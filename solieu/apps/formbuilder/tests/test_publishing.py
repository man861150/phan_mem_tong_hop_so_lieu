from io import StringIO

from django.core.management import call_command

from apps.formbuilder.models import FormRule, FormTemplate
from apps.formbuilder.services import add_field, publish_template
from apps.formbuilder.tests.base import FormFixture


class PublishTests(FormFixture):
    def test_invalid_publish_keeps_the_draft(self):
        template = self.make_template(
            name="Tháng", function_type="thang", activity_type=None
        )
        client = self.login(self.head)
        response = client.post(f"/bieu-mau/{template.pk}/xuat-ban/")
        self.assertContains(response, "Chưa xuất bản được.")
        template.refresh_from_db()
        self.assertIsNone(template.current_published_id)

    def test_valid_publish_creates_the_next_draft(self):
        template = self.make_template()
        client = self.login(self.head)
        response = client.post(f"/bieu-mau/{template.pk}/xuat-ban/")
        self.assertRedirects(response, f"/bieu-mau/{template.pk}/thiet-ke/")
        template.refresh_from_db()
        self.assertEqual(template.current_published.version, 1)
        self.assertEqual(template.current_draft.version, 2)
        self.assertEqual(template.current_draft.status, "draft")

    def test_choice_without_options_and_cycles_block_publish(self):
        template = self.make_template()
        draft = template.current_draft
        select = add_field(draft, "select", draft.sections.get(), label="Kênh")
        response = self.login(self.head).post(f"/bieu-mau/{template.pk}/xuat-ban/")
        self.assertContains(response, "cần ít nhất một lựa chọn")
        select.options.create(label="A", value="a", order=1)
        other = add_field(draft, "text", draft.sections.get(), label="Ghi chú thêm")
        FormRule.objects.create(
            version=draft,
            source_field_key=select.key,
            operator="equals",
            compare_value="a",
            action="require",
            target_field_key=other.key,
            order=1,
        )
        FormRule.objects.create(
            version=draft,
            source_field_key=other.key,
            operator="is_not_empty",
            action="show",
            target_field_key=select.key,
            order=2,
        )
        blocked = self.login(self.head).post(f"/bieu-mau/{template.pk}/xuat-ban/")
        self.assertContains(blocked, "vòng lặp")
        template.refresh_from_db()
        self.assertIsNone(template.current_published_id)

    def test_duplicate_archive_and_restore(self):
        template = self.make_template()
        publish_template(template, self.head)
        template.refresh_from_db()
        client = self.login(self.head)
        copied = client.post(f"/bieu-mau/{template.pk}/nhan-ban/")
        copy = FormTemplate.objects.exclude(pk=template.pk).get()
        self.assertRedirects(copied, f"/bieu-mau/{copy.pk}/thiet-ke/")
        self.assertFalse(copy.is_active)
        self.assertIn("bản sao", copy.name)
        self.assertEqual(
            copy.current_draft.fields.count(), template.current_published.fields.count()
        )
        self.assertEqual(
            copy.current_draft.rules.count(), template.current_published.rules.count()
        )
        client.post(f"/bieu-mau/{template.pk}/luu-tru/")
        template.refresh_from_db()
        self.assertFalse(template.is_active)
        self.assertEqual(template.versions.count(), 2)
        restored = client.post(f"/bieu-mau/{copy.pk}/khoi-phuc/")
        self.assertRedirects(restored, f"/bieu-mau/{copy.pk}/thiet-ke/")
        copy.refresh_from_db()
        self.assertTrue(copy.is_active)
        blocked = client.post(f"/bieu-mau/{template.pk}/khoi-phuc/", follow=True)
        self.assertContains(blocked, "Đã có biểu mẫu đang hoạt động cho phạm vi này.")

    def test_draft_from_version_replaces_the_draft_only(self):
        template = self.make_template()
        published = publish_template(template, self.head)
        template.refresh_from_db()
        draft = template.current_draft
        add_field(draft, "text", draft.sections.get(), label="Chỉ ở nháp")
        client = self.login(self.head)
        client.post(
            f"/bieu-mau/{template.pk}/phien-ban/{published.pk}/lam-nhap/",
        )
        template.refresh_from_db()
        self.assertFalse(
            template.current_draft.fields.filter(label="Chỉ ở nháp").exists()
        )
        self.assertEqual(template.current_published_id, published.pk)

    def test_seed_command_is_idempotent(self):
        call_command("seed_form_templates", stdout=StringIO())
        call_command("seed_form_templates", stdout=StringIO())
        template = FormTemplate.objects.get(
            phong=self.htkn,
            scope_key=f"hoat_dong:loai:{self.loai.pk}",
            is_active=True,
        )
        self.assertEqual(template.current_published.version, 1)
        self.assertEqual(template.current_draft.version, 2)
        published_keys = set(
            template.current_published.fields.values_list("key", flat=True)
        )
        self.assertIn("cf_so_luong_dai_bieu", published_keys)
        self.assertIn("cf_duong_dan_phong_hop", published_keys)
        self.assertNotIn("cf_ghi_chu_noi_bo", published_keys)
        self.assertTrue(
            template.current_draft.fields.filter(key="cf_ghi_chu_noi_bo").exists()
        )
        rule = template.current_published.rules.get()
        self.assertEqual(rule.compare_value, "Trực tuyến")
        self.assertEqual(rule.action, "require")
