"""Published templates on the existing activity, month, and project screens."""

from datetime import date
from decimal import Decimal

from django.core.files.uploadedfile import SimpleUploadedFile

from apps.activities.models import ChuongTrinhDuAn, DuAn, HinhThucDuAn
from apps.catalog.models import (
    BieuMauChiTieu,
    CachTongHop,
    ChiTieu,
    KieuGhiNhan,
    KyBaoCao,
    LoaiHoTro,
    TrangThaiKy,
)
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LichSuXuLy,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)
from apps.formbuilder.models import FormAttachment, FormValue
from apps.formbuilder.services import add_field, archive_template, publish_template
from apps.formbuilder.tests.base import FormFixture


class EntryIntegrationTests(FormFixture):
    def _published_activity_template(self, **field_kwargs):
        template = self.make_template()
        draft = template.current_draft
        field = add_field(
            draft,
            "integer",
            draft.sections.get(),
            label="Số lượng đại biểu",
            key="cf_so_luong_dai_bieu",
        )
        field.required = True
        field.min_value = 0
        for name, value in field_kwargs.items():
            setattr(field, name, value)
        field.save()
        publish_template(template, self.head)
        template.refresh_from_db()
        return template, field

    def test_missing_template_keeps_the_fixed_form(self):
        activity = self.make_activity()
        page = self.login(self.officer).get(f"/phieu/hoat-dong/{activity.pk}/")
        self.assertEqual(page.status_code, 200)
        self.assertNotContains(page, "Số lượng đại biểu")
        self.assertContains(page, "Lưu nháp")

    def test_required_custom_field_blocks_submit_and_allows_draft(self):
        self._published_activity_template()
        activity = self.make_activity()
        url = f"/phieu/hoat-dong/{activity.pk}/"
        client = self.login(self.officer)
        opened = client.get(url)
        self.assertContains(opened, "Số lượng đại biểu")
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        draft = client.post(url, {"action": "save"})
        self.assertRedirects(draft, f"{url}?phieu={phieu.pk}")
        phieu.refresh_from_db()
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertFalse(LichSuXuLy.objects.filter(phieu=phieu).exists())

        blocked = client.post(url, {"action": "gui"})
        self.assertEqual(blocked.status_code, 200)
        self.assertContains(blocked, "Vui lòng nhập Số lượng đại biểu.")
        phieu.refresh_from_db()
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertFalse(LichSuXuLy.objects.filter(phieu=phieu).exists())

        sent = client.post(url, {"action": "gui", "cf_so_luong_dai_bieu": "12"})
        self.assertRedirects(sent, f"{url}?phieu={phieu.pk}")
        phieu.refresh_from_db()
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.CHO_DUYET)
        self.assertEqual(
            LichSuXuLy.objects.filter(phieu=phieu, hanh_dong=HanhDongXuLy.GUI).count(),
            1,
        )
        stored = FormValue.objects.get(
            response__phieu=phieu, field_key="cf_so_luong_dai_bieu"
        )
        self.assertEqual(stored.value_number, Decimal("12"))
        self.assertEqual(stored.response.template_version.version, 1)

        detail = self.login(self.head).get(f"/phieu/{phieu.pk}/")
        self.assertContains(detail, "Số lượng đại biểu")
        self.assertContains(detail, "12")
        history = client.get(f"/phieu/{phieu.pk}/lich-su/")
        self.assertContains(history, "Số lượng đại biểu")
        queue = self.login(self.head).get("/duyet/")
        self.assertContains(queue, activity.ten)

    def test_later_publish_and_archive_keep_the_old_phieu(self):
        template, _field = self._published_activity_template()
        activity = self.make_activity()
        url = f"/phieu/hoat-dong/{activity.pk}/"
        client = self.login(self.officer)
        client.get(url)
        client.post(url, {"action": "gui", "cf_so_luong_dai_bieu": "8"})
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        draft = template.current_draft
        add_field(
            draft,
            "text",
            draft.sections.get(),
            label="Chỉ ở phiên bản 2",
            key="cf_chi_o_v2",
        )
        publish_template(template, self.head)
        detail = client.get(f"/phieu/{phieu.pk}/")
        self.assertContains(detail, "Số lượng đại biểu")
        self.assertNotContains(detail, "Chỉ ở phiên bản 2")
        self.assertContains(detail, "Phiên bản 1")

        newer = self.make_activity(ten="Lớp mới")
        opened = client.get(f"/phieu/hoat-dong/{newer.pk}/")
        self.assertContains(opened, "Chỉ ở phiên bản 2")
        archive_template(template)
        after = client.get(
            f"/phieu/hoat-dong/{self.make_activity(ten='Lớp sau lưu trữ').pk}/"
        )
        self.assertNotContains(after, "Chỉ ở phiên bản 2")
        self.assertContains(client.get(f"/phieu/{phieu.pk}/"), "Số lượng đại biểu")

    def test_file_download_stays_inside_the_department(self):
        template = self.make_template()
        draft = template.current_draft
        field = add_field(
            draft,
            "file",
            draft.sections.get(),
            label="Tài liệu đính kèm",
            key="cf_tai_lieu",
        )
        field.allowed_extensions = "pdf,docx"
        field.max_file_size_mb = 10
        field.save()
        publish_template(template, self.head)
        activity = self.make_activity()
        url = f"/phieu/hoat-dong/{activity.pk}/"
        client = self.login(self.officer)
        client.get(url)
        saved = client.post(
            url,
            {
                "action": "save",
                "cf_tai_lieu": SimpleUploadedFile(
                    "tai lieu.pdf",
                    b"%PDF-1.4",
                    content_type="application/pdf",
                ),
            },
        )
        self.assertEqual(saved.status_code, 302)
        attachment = FormAttachment.objects.get()
        self.assertNotIn("/", attachment.original_name)
        self.assertNotIn("\\", attachment.original_name)
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        detail = client.get(f"/phieu/{phieu.pk}/")
        self.assertContains(detail, attachment.original_name)
        download = client.get(f"/bieu-mau/tep/{attachment.pk}/")
        self.assertEqual(download.status_code, 200)
        self.assertIn(attachment.original_name, download["Content-Disposition"])
        other = self.login(self.head_other).get(f"/bieu-mau/tep/{attachment.pk}/")
        self.assertEqual(other.status_code, 404)

    def test_per_row_value_uses_the_indicator_total(self):
        indicator = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-HL-1",
            ten_chi_tieu="Số học viên",
            don_vi_tinh="người",
            nhom=self.nhom,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
        )
        BieuMauChiTieu.objects.create(
            loai_hoat_dong=self.loai,
            chi_tieu=indicator,
            bat_buoc=False,
            thu_tu=1,
        )
        template = self.make_template(
            name="Cột chỉ tiêu",
            function_type="chi_tieu",
            activity_type=None,
            group=self.nhom,
        )
        draft = template.current_draft
        add_field(
            draft,
            "integer",
            draft.sections.get(),
            label="Số nhóm",
            key="cf_so_nhom",
        )
        publish_template(template, self.head)
        activity = self.make_activity()
        url = f"/phieu/hoat-dong/{activity.pk}/"
        client = self.login(self.officer)
        client.get(url)
        response = client.post(
            url,
            {
                "action": "save",
                f"gia_tri_{indicator.pk}": "20",
                f"cf_so_nhom__ct_{indicator.pk}": "3",
            },
        )
        self.assertEqual(response.status_code, 302, response.content[:500])
        total = SoLieu.objects.get(
            phieu__hoat_dong=activity,
            chi_tieu=indicator,
            doi_tuong=None,
            linh_vuc=None,
        )
        value = FormValue.objects.get(field_key="cf_so_nhom")
        self.assertEqual(value.so_lieu_id, total.pk)
        self.assertEqual(value.value_number, Decimal("3"))

    def test_month_and_project_forms_use_their_templates(self):
        month = self.make_template(
            name="Báo cáo tháng",
            function_type="thang",
            activity_type=None,
        )
        draft = month.current_draft
        note = add_field(
            draft,
            "textarea",
            draft.sections.get(),
            label="Ghi chú tháng",
            key="cf_ghi_chu_thang",
        )
        note.required = True
        note.save()
        publish_template(month, self.head)
        period = KyBaoCao.objects.create(
            nam=2026,
            so_ky=11,
            trang_thai=TrangThaiKy.MO,
        )
        client = self.login(self.officer)
        month_url = f"/phieu/thang/{period.pk}/"
        opened = client.get(month_url)
        self.assertContains(opened, "Ghi chú tháng")
        blocked = client.post(month_url, {"action": "gui"})
        self.assertContains(blocked, "Vui lòng nhập Ghi chú tháng.")
        phieu = PhieuNhapLieu.objects.get(ky=period, phong=self.htkn)
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertFalse(LichSuXuLy.objects.filter(phieu=phieu).exists())
        saved = client.post(month_url, {"action": "save", "cf_ghi_chu_thang": "Đủ số"})
        self.assertEqual(saved.status_code, 302)

        project_template = self.make_template(
            name="Dự án",
            function_type="du_an",
            activity_type=None,
        )
        project_draft = project_template.current_draft
        extra = add_field(
            project_draft,
            "text",
            project_draft.sections.get(),
            label="Mã hồ sơ",
            key="cf_ma_ho_so",
        )
        extra.required = True
        extra.save()
        publish_template(project_template, self.head)
        project = DuAn.objects.create(
            phong=self.htkn,
            ten_du_an="Dự án mẫu",
            chuong_trinh=ChuongTrinhDuAn.NQ20,
            hinh_thuc=HinhThucDuAn.UOM_TAO,
            nam=2026,
        )
        project_url = f"/phieu/du-an/{project.pk}/"
        page = client.get(project_url)
        self.assertContains(page, "Mã hồ sơ")
        refused = client.post(project_url, {"action": "gui"})
        self.assertContains(refused, "Vui lòng nhập Mã hồ sơ.")
        project_phieu = PhieuNhapLieu.objects.get(du_an=project)
        self.assertEqual(project_phieu.loai_phieu, LoaiPhieu.DU_AN)
        self.assertEqual(project_phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertFalse(LichSuXuLy.objects.filter(phieu=project_phieu).exists())
        HoTroDuAn.objects.create(
            du_an=project,
            phieu=project_phieu,
            loai_ho_tro=LoaiHoTro.DICH_VU,
            noi_dung="Tư vấn",
            ngay_ho_tro=date(2026, 11, 15),
        )
        sent = client.post(
            project_url,
            {"action": "gui", "cf_ma_ho_so": "HS-11"},
        )
        self.assertEqual(sent.status_code, 302)
        project_phieu.refresh_from_db()
        self.assertEqual(project_phieu.trang_thai, TrangThaiPhieu.CHO_DUYET)
        detail = client.get(f"/phieu/{project_phieu.pk}/")
        self.assertContains(detail, "Mã hồ sơ")
        self.assertContains(detail, "HS-11")
