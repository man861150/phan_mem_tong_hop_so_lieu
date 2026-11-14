from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.activities.models import DonViPhoiHop
from apps.catalog.models import CachTongHop, ChiTieu, KieuGhiNhan
from apps.formbuilder.forms import DynamicEntryForm
from apps.formbuilder.models import FormRule, FormValue
from apps.formbuilder.services import (
    add_field,
    add_option,
    load_version,
)
from apps.formbuilder.tests.base import FormFixture
from apps.formbuilder.values import evaluate_rules, render_readonly


class RenderingTests(FormFixture):
    def _version_with_fields(self):
        template = self.make_template(name="Đủ kiểu", activity_type=None)
        draft = template.current_draft
        section = draft.sections.get()
        created = {}
        for field_type, label in (
            ("text", "Tên ngắn"),
            ("textarea", "Mô tả dài"),
            ("integer", "Số nguyên"),
            ("decimal", "Số lẻ"),
            ("percent", "Tỷ lệ"),
            ("date", "Ngày"),
            ("time", "Giờ"),
            ("datetime", "Ngày giờ"),
            ("select", "Chọn một danh sách"),
            ("multi_select", "Chọn nhiều mục"),
            ("radio", "Chọn radio"),
            ("checkbox", "Đồng ý"),
            ("switch", "Bật"),
            ("email", "Hòm thư"),
            ("phone", "Điện thoại"),
            ("url", "Trang web"),
            ("file", "Tệp đính kèm"),
            ("image", "Ảnh"),
            ("lookup", "Đối tượng"),
            ("instruction", "Hướng dẫn"),
        ):
            field = add_field(draft, field_type, section, label=label)
            created[field_type] = field
        for field_type in ("select", "multi_select", "radio"):
            add_option(created[field_type], "Một", "mot")
            add_option(created[field_type], "Hai", "hai")
        created["file"].allowed_extensions = "pdf,docx"
        created["file"].max_file_size_mb = 10
        created["file"].save()
        created["image"].allowed_extensions = "png"
        created["image"].save()
        created["lookup"].catalog_source = "don_vi_phoi_hop"
        created["lookup"].save()
        created["text"].regex = r"^Mau-\d+$"
        created["text"].save()
        created["integer"].min_value = 0
        created["integer"].required = True
        created["integer"].save()
        return template, created

    def test_each_type_round_trips_and_rejects_bad_input(self):
        template, fields = self._version_with_fields()
        partner = DonViPhoiHop.objects.create(ten_don_vi="Sở Khoa học")
        phieu = self.make_phieu()
        version = load_version(template.current_draft)
        data = {
            fields["text"].key: "Mau-12",
            fields["textarea"].key: "Nội dung",
            fields["integer"].key: "4",
            fields["decimal"].key: "1.5",
            fields["percent"].key: "80",
            fields["date"].key: "2026-11-14",
            fields["time"].key: "09:30",
            fields["datetime"].key: "2026-11-14T09:30",
            fields["select"].key: "mot",
            fields["radio"].key: "hai",
            fields["email"].key: "a@sihub.vn",
            fields["phone"].key: "0903 000 111",
            fields["url"].key: "https://sihub.vn",
            fields["lookup"].key: str(partner.pk),
            fields["checkbox"].key: "on",
            fields["switch"].key: "on",
        }
        files = {
            fields["file"].key: SimpleUploadedFile(
                "tai-lieu.pdf", b"%PDF-1.4", content_type="application/pdf"
            ),
            fields["image"].key: SimpleUploadedFile(
                "anh.png", b"\x89PNG\r\n", content_type="image/png"
            ),
        }
        form = DynamicEntryForm(
            data,
            files,
            version=version,
            phieu=phieu,
            enforce_required=True,
        )
        form.data = _Query(data)
        self.assertTrue(form.is_valid(), form.errors)
        form.save(phieu, self.officer)
        stored = {
            row.field_key: row
            for row in FormValue.objects.filter(response__phieu=phieu)
        }
        self.assertEqual(stored[fields["integer"].key].value_number, Decimal("4"))
        self.assertEqual(stored[fields["percent"].key].value_number, Decimal("80"))
        self.assertEqual(stored[fields["phone"].key].value_text, "0903000111")
        self.assertEqual(stored[fields["lookup"].key].value_text, str(partner.pk))
        self.assertTrue(stored[fields["checkbox"].key].value_bool)
        self.assertEqual(stored[fields["select"].key].value_text, "mot")
        self.assertTrue(stored[fields["file"].key].attachments.exists())
        multi = DynamicEntryForm(
            _Query({fields["multi_select"].key: ["mot", "hai"]}),
            None,
            version=version,
            phieu=phieu,
            enforce_required=False,
        )
        self.assertTrue(multi.is_valid(), multi.errors)
        multi.save(phieu, self.officer)
        multi_row = FormValue.objects.get(field=fields["multi_select"])
        self.assertEqual(multi_row.value_json, ["mot", "hai"])
        rendered = render_readonly(phieu.form_responses.get(template=template))
        labels = [
            item["label"]
            for section in rendered["sections"]
            for item in section["items"]
        ]
        self.assertIn("Số nguyên", labels)
        self.assertIn("Hướng dẫn", labels)
        bad = DynamicEntryForm(
            {
                "cf_unused": "no",
                fields["integer"].key: "1.5",
                fields["email"].key: "khong-phai-email",
            },
            None,
            version=version,
            phieu=phieu,
            enforce_required=True,
        )
        self.assertFalse(bad.is_valid())
        self.assertIn(fields["integer"].key, bad.errors)

    def test_rules_hide_and_require_on_the_server(self):
        template, fields = self._version_with_fields()
        draft = template.current_draft
        note = fields["textarea"]
        source = fields["select"]
        FormRule.objects.create(
            version=draft,
            source_field_key=source.key,
            operator="equals",
            compare_value="hai",
            action="hide",
            target_field_key=note.key,
            order=1,
        )
        FormRule.objects.create(
            version=draft,
            source_field_key=source.key,
            operator="equals",
            compare_value="mot",
            action="require",
            target_field_key=note.key,
            order=2,
        )
        version = load_version(draft)
        phieu = self.make_phieu()
        visible, required = evaluate_rules(
            list(version.fields.all()),
            list(version.rules.all()),
            {source.key: "mot"},
        )
        self.assertTrue(required[note.key])
        self.assertTrue(visible[note.key])
        hidden = DynamicEntryForm(
            {source.key: "hai", note.key: "bí mật", fields["integer"].key: "1"},
            None,
            version=version,
            phieu=phieu,
            enforce_required=True,
        )
        self.assertTrue(hidden.is_valid(), hidden.errors)
        hidden.save(phieu, self.officer)
        self.assertFalse(FormValue.objects.filter(field=note).exists())
        shown = DynamicEntryForm(
            {source.key: "mot", fields["integer"].key: "1"},
            None,
            version=version,
            phieu=phieu,
            enforce_required=True,
        )
        self.assertFalse(shown.is_valid())
        self.assertIn("Vui lòng nhập", shown.errors[note.key][0])

    def test_lookup_rejects_an_object_outside_the_department(self):
        template = self.make_template(
            name="Chỉ tiêu",
            function_type="chi_tieu",
            activity_type=None,
            group=self.nhom,
        )
        other = ChiTieu.objects.create(
            ma_chi_tieu="GDCN-X",
            ten_chi_tieu="Chỉ tiêu phòng khác",
            don_vi_tinh="cái",
            nhom=self.nhom_other,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
        )
        field = template.current_draft.fields.filter(source="custom").first()
        if field is None:
            field = add_field(
                template.current_draft,
                "lookup",
                template.current_draft.sections.get(),
                label="Chỉ tiêu",
            )
        field.field_type = "lookup"
        field.catalog_source = "chi_tieu"
        field.save()
        version = load_version(template.current_draft)
        posted_name = f"{field.key}__ct_{other.pk}"
        form = DynamicEntryForm(
            {posted_name: str(other.pk)},
            None,
            version=version,
            phieu=self.make_phieu(),
            enforce_required=False,
            mode="row",
            indicator_ids=[other.pk],
        )
        self.assertFalse(form.is_valid())

    def test_percent_email_phone_and_file_limits(self):
        template, fields = self._version_with_fields()
        version = load_version(template.current_draft)
        phieu = self.make_phieu()
        form = DynamicEntryForm(
            {
                fields["percent"].key: "140",
                fields["email"].key: "sai",
                fields["phone"].key: "123",
                fields["url"].key: "khong-phai-url",
                fields["date"].key: "32/13/2026",
                fields["text"].key: "sai-dinh-dang",
                fields["integer"].key: "2",
            },
            {
                fields["file"].key: SimpleUploadedFile(
                    "virus.exe",
                    b"abc",
                    content_type="application/octet-stream",
                )
            },
            version=version,
            phieu=phieu,
            enforce_required=True,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(fields["percent"].key, form.errors)
        self.assertIn(fields["file"].key, form.errors)


class _Query(dict):
    def getlist(self, key):
        value = self.get(key, [])
        if isinstance(value, list):
            return value
        return [value]
