"""Activity types, activities, partner units, and projects."""

from datetime import date

from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import (
    DonViPhoiHop,
    DuAn,
    HoatDong,
    HoatDongDonVi,
    TrangThaiHoatDong,
)
from apps.catalog.models import LoaiHoatDong, PhongBan


class ActivityFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.htkn = PhongBan.objects.create(ma_phong="HTKN", ten_phong="Phòng HTKN")
        cls.gdcn = PhongBan.objects.create(ma_phong="GDCN", ten_phong="Phòng GDCN")
        cls.loai_htkn = LoaiHoatDong.objects.create(
            phong=cls.htkn,
            ten_loai="Lớp huấn luyện",
        )
        cls.loai_gdcn = LoaiHoatDong.objects.create(
            phong=cls.gdcn,
            ten_loai="Techmart",
        )
        cls.loai_ad_hoc = LoaiHoatDong.objects.create(
            phong=cls.htkn,
            ten_loai="Nhiệm vụ phát sinh",
        )
        cls.cb_htkn = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Cán bộ HTKN",
            role=Role.ENTRY_OFFICER,
            phong=cls.htkn,
            password="test-pass-1",
        )
        cls.cb_gdcn = User.objects.create_user(
            username="cb.gdcn",
            ho_ten="Cán bộ GDCN",
            role=Role.ENTRY_OFFICER,
            phong=cls.gdcn,
            password="test-pass-1",
        )
        cls.center = User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo Trung tâm",
            role=Role.CENTER_HEAD,
            password="test-pass-1",
        )
        cls.don_vi = DonViPhoiHop.objects.create(ten_don_vi="Vườn ươm ABC")

    def make_activity(self, **overrides):
        values = {
            "loai_hoat_dong": self.loai_htkn,
            "ten": "Lớp khởi nghiệp tháng 11",
            "tu_ngay": date(2026, 11, 5),
            "den_ngay": date(2026, 11, 7),
            "dia_diem": "Trung tâm Khởi nghiệp",
        }
        values.update(overrides)
        return HoatDong.objects.create(**values)

    def login(self, user):
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        return client


class HoatDongModelTests(ActivityFixtureMixin, TestCase):
    def test_end_date_defaults_to_start_date(self):
        activity = self.make_activity(den_ngay=None)
        self.assertEqual(activity.den_ngay, activity.tu_ngay)

    def test_end_date_before_start_date_is_rejected(self):
        activity = HoatDong(
            loai_hoat_dong=self.loai_htkn,
            ten="Sai ngày",
            tu_ngay=date(2026, 11, 10),
            den_ngay=date(2026, 11, 9),
        )
        with self.assertRaises(ValidationError):
            activity.save()

    def test_ad_hoc_requires_text_before_organized(self):
        activity = self.make_activity(
            loai_hoat_dong=self.loai_ad_hoc,
            ten="Nhiệm vụ đột xuất",
        )
        activity.trang_thai = TrangThaiHoatDong.DA_TO_CHUC
        with self.assertRaises(ValidationError) as caught:
            activity.save()
        self.assertIn("noi_dung", caught.exception.message_dict)
        self.assertIn("ket_qua", caught.exception.message_dict)

    def test_other_activity_types_do_not_require_ad_hoc_text(self):
        activity = self.make_activity()
        activity.trang_thai = TrangThaiHoatDong.DA_TO_CHUC
        activity.save()
        activity.refresh_from_db()
        self.assertEqual(activity.trang_thai, TrangThaiHoatDong.DA_TO_CHUC)


class HoatDongViewTests(ActivityFixtureMixin, TestCase):
    def test_entry_officer_creates_activity_with_partner(self):
        client = self.login(self.cb_htkn)
        response = client.post(
            "/hoat-dong/tao/",
            {
                "loai_hoat_dong": self.loai_htkn.pk,
                "ten": "Lớp khởi nghiệp tháng 11",
                "tu_ngay": "2026-11-05",
                "den_ngay": "2026-11-07",
                "dia_diem": "Trung tâm Khởi nghiệp",
                "hinh_thuc": "truc_tiep",
                "don_vi_phoi_hop": [self.don_vi.pk],
            },
        )
        self.assertEqual(response.status_code, 302)
        activity = HoatDong.objects.get(ten="Lớp khởi nghiệp tháng 11")
        self.assertEqual(activity.trang_thai, TrangThaiHoatDong.KE_HOACH)
        self.assertTrue(
            HoatDongDonVi.objects.filter(
                hoat_dong=activity,
                don_vi=self.don_vi,
            ).exists()
        )

    def test_list_and_detail_are_scoped(self):
        activity = self.make_activity()
        client = self.login(self.cb_gdcn)
        response = client.get("/hoat-dong/")
        self.assertNotContains(response, activity.ten)
        response = client.get(f"/hoat-dong/{activity.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_create_type_choices_are_department_scoped(self):
        response = self.login(self.cb_htkn).get("/hoat-dong/tao/")
        self.assertContains(response, "Lớp huấn luyện")
        self.assertNotContains(response, "Techmart")

    def test_center_head_is_read_only(self):
        activity = self.make_activity()
        client = self.login(self.center)
        response = client.get(f"/hoat-dong/{activity.pk}/")
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Lưu hoạt động")
        response = client.post(f"/hoat-dong/{activity.pk}/", {"ten": "Đổi tên"})
        self.assertEqual(response.status_code, 403)

    def test_center_head_cannot_transition(self):
        activity = self.make_activity()
        response = self.login(self.center).post(
            f"/hoat-dong/{activity.pk}/da-to-chuc/"
        )
        self.assertEqual(response.status_code, 403)

    def test_transition_records_history(self):
        activity = self.make_activity()
        response = self.login(self.cb_htkn).post(
            f"/hoat-dong/{activity.pk}/da-to-chuc/"
        )
        self.assertEqual(response.status_code, 302)
        activity.refresh_from_db()
        self.assertEqual(activity.trang_thai, TrangThaiHoatDong.DA_TO_CHUC)
        self.assertIn(
            TrangThaiHoatDong.KE_HOACH,
            list(activity.history.values_list("trang_thai", flat=True)),
        )

    def test_partner_add_is_idempotent_and_checks_existing(self):
        client = self.login(self.cb_htkn)
        response = client.post(
            "/hoat-dong/don-vi/them/",
            {
                "ten_don_vi_moi": "  Vườn ươm XYZ  ",
                "don_vi_phoi_hop": [self.don_vi.pk],
            },
        )
        self.assertEqual(response.status_code, 200)
        added = DonViPhoiHop.objects.get(ten_don_vi="Vườn ươm XYZ")
        self.assertContains(response, f'value="{added.pk}" checked')
        response = client.post(
            "/hoat-dong/don-vi/them/",
            {
                "ten_don_vi_moi": "VƯỜN ƯƠM xyz",
                "don_vi_phoi_hop": [self.don_vi.pk],
            },
        )
        self.assertEqual(
            DonViPhoiHop.objects.filter(ten_don_vi__iexact="Vườn ươm XYZ").count(),
            1,
        )
        self.assertContains(response, f'value="{added.pk}" checked')

    def test_center_head_cannot_add_partner(self):
        response = self.login(self.center).post(
            "/hoat-dong/don-vi/them/",
            {"ten_don_vi_moi": "Không được phép"},
        )
        self.assertEqual(response.status_code, 403)


class DuAnViewTests(ActivityFixtureMixin, TestCase):
    def test_entry_officer_creates_project(self):
        response = self.login(self.cb_htkn).post(
            "/du-an/tao/",
            {
                "phong": self.htkn.pk,
                "ten_du_an": "Startup A",
                "chuong_trinh": "nq20",
                "hinh_thuc": "uom_tao",
                "nam": "2026",
            },
        )
        self.assertEqual(response.status_code, 302)
        project = DuAn.objects.get(ten_du_an="Startup A")
        self.assertEqual(project.phong, self.htkn)
        self.assertTrue(project.history.exists())

    def test_project_list_and_detail_are_scoped(self):
        project = DuAn.objects.create(
            phong=self.htkn,
            ten_du_an="Startup A",
            chuong_trinh="nq20",
            hinh_thuc="uom_tao",
            nam=2026,
        )
        client = self.login(self.cb_gdcn)
        response = client.get("/du-an/")
        self.assertNotContains(response, project.ten_du_an)
        response = client.get(f"/du-an/{project.pk}/")
        self.assertEqual(response.status_code, 404)

    def test_center_head_can_view_but_not_edit_project(self):
        project = DuAn.objects.create(
            phong=self.htkn,
            ten_du_an="Startup A",
            chuong_trinh="nq20",
            hinh_thuc="uom_tao",
            nam=2026,
        )
        client = self.login(self.center)
        response = client.get("/du-an/")
        self.assertContains(response, project.ten_du_an)
        self.assertNotContains(response, "Thêm dự án")
        response = client.get(f"/du-an/{project.pk}/")
        self.assertNotContains(response, "Lưu dự án")
        response = client.post(
            f"/du-an/{project.pk}/",
            {
                "phong": self.htkn.pk,
                "ten_du_an": "Đổi tên",
                "chuong_trinh": "nq20",
                "hinh_thuc": "uom_tao",
                "nam": "2026",
            },
        )
        self.assertEqual(response.status_code, 403)
