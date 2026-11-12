"""Data-entry forms, indicator rows, project support, and approvals."""

from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import DuAn, HoatDong, TrangThaiHoatDong
from apps.catalog.models import (
    BieuMauChiTieu,
    CachTongHop,
    ChiTieu,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    KieuGhiNhan,
    KyBaoCao,
    LoaiHoatDong,
    NguonSoLieu,
    NhomChiTieu,
    PhongBan,
    TrangThaiKy,
)
from apps.entry.forms import ActivityEntryForm
from apps.entry.models import (
    HoTroDuAn,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)


class EntryFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.htkn = PhongBan.objects.create(ma_phong="HTKN", ten_phong="Phòng HTKN")
        cls.gdcn = PhongBan.objects.create(ma_phong="GDCN", ten_phong="Phòng GDCN")
        cls.tttk = PhongBan.objects.create(ma_phong="TTTK", ten_phong="Phòng TTTK")

        cls.loai_htkn = LoaiHoatDong.objects.create(
            phong=cls.htkn,
            ten_loai="Lớp huấn luyện",
        )
        cls.loai_ad_hoc = LoaiHoatDong.objects.create(
            phong=cls.htkn,
            ten_loai="Nhiệm vụ phát sinh",
        )
        cls.loai_gdcn = LoaiHoatDong.objects.create(
            phong=cls.gdcn,
            ten_loai="Techmart",
        )

        cls.nhom_htkn = NhomChiTieu.objects.create(
            phong=cls.htkn,
            ten_mang="HTKN-HL",
        )
        cls.nhom_gdcn = NhomChiTieu.objects.create(
            phong=cls.gdcn,
            ten_mang="GDCN-SAN",
        )
        cls.nhom_tttk = NhomChiTieu.objects.create(
            phong=cls.tttk,
            ten_mang="TTTK-1",
        )

        cls.nguon_event = NguonSoLieu.objects.create(ten_nguon="Tại sự kiện")
        cls.nguon_survey = NguonSoLieu.objects.create(
            ten_nguon="Phiếu khảo sát sau sự kiện"
        )

        cls.obj_dn = DanhMucDoiTuong.objects.create(ten_doi_tuong="Doanh nghiệp")
        cls.obj_sv = DanhMucDoiTuong.objects.create(
            ten_doi_tuong="Sinh viên/Học viên"
        )
        cls.lv_qd36 = DanhMucLinhVuc.objects.create(
            he_thong="qd36",
            ma="QD36-01",
            ten="Công nghệ thông tin",
            cap=1,
        )
        cls.lv_qd36b = DanhMucLinhVuc.objects.create(
            he_thong="qd36",
            ma="QD36-02",
            ten="Công nghệ sinh học",
            cap=1,
        )
        cls.lv_tt24 = DanhMucLinhVuc.objects.create(
            he_thong="tt24",
            ma="TT24-01",
            ten="Khoa học tự nhiên",
            cap=1,
        )
        cls.lv_tt24b = DanhMucLinhVuc.objects.create(
            he_thong="tt24",
            ma="TT24-02",
            ten="Khoa học kỹ thuật",
            cap=1,
        )

        cls.count_lop = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-LOP",
            ten_chi_tieu="Số lớp huấn luyện",
            don_vi_tinh="lớp",
            nhom=cls.nhom_htkn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.COUNT,
            count_subject="activity",
            loai_hoat_dong=cls.loai_htkn,
        )
        cls.hv = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-LOP-HV",
            ten_chi_tieu="Số học viên tham gia",
            don_vi_tinh="người",
            nhom=cls.nhom_htkn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
            chi_tieu_cha=cls.count_lop,
        )
        cls.cn = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-LOP-CN",
            ten_chi_tieu="Số học viên được cấp chứng nhận",
            don_vi_tinh="người",
            nhom=cls.nhom_htkn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
            chi_tieu_cha=cls.count_lop,
            khong_vuot_chi_tieu=cls.hv,
        )
        cls.cg = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-LOP-CG",
            ten_chi_tieu="Số chuyên gia/giảng viên tham gia",
            don_vi_tinh="người",
            nhom=cls.nhom_htkn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
            chi_tieu_cha=cls.count_lop,
        )
        cls.ks = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-LOP-KS",
            ten_chi_tieu="Số học viên tham gia khảo sát",
            don_vi_tinh="người",
            nhom=cls.nhom_htkn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
            chi_tieu_cha=cls.count_lop,
            khong_vuot_chi_tieu=cls.hv,
        )
        cls.hv.nguon_cho_phep.add(cls.nguon_survey)
        for order, chi_tieu in enumerate(
            (cls.hv, cls.cn, cls.cg, cls.ks),
            start=1,
        ):
            BieuMauChiTieu.objects.create(
                loai_hoat_dong=cls.loai_htkn,
                chi_tieu=chi_tieu,
                bat_buoc=True,
                thu_tu=order,
            )

        cls.gdcn_indicator = ChiTieu.objects.create(
            ma_chi_tieu="GDCN-TM-GH",
            ten_chi_tieu="Số gian hàng",
            don_vi_tinh="gian hàng",
            nhom=cls.nhom_gdcn,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
        )
        BieuMauChiTieu.objects.create(
            loai_hoat_dong=cls.loai_gdcn,
            chi_tieu=cls.gdcn_indicator,
            bat_buoc=True,
            thu_tu=1,
        )

        cls.ndt = ChiTieu.objects.create(
            ma_chi_tieu="TTTK-NDT",
            ten_chi_tieu="Số người dùng tin đang phục vụ",
            don_vi_tinh="người",
            nhom=cls.nhom_tttk,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
            cach_tong_hop=CachTongHop.CUMULATIVE,
            phan_loai_doi_tuong=True,
            phan_loai_linh_vuc=True,
        )
        cls.ndt.doi_tuong_ap_dung.set([cls.obj_dn, cls.obj_sv])

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
        cls.cb_tttk = User.objects.create_user(
            username="cb.tttk",
            ho_ten="Cán bộ TTTK",
            role=Role.ENTRY_OFFICER,
            phong=cls.tttk,
            password="test-pass-1",
        )
        cls.center = User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo Trung tâm",
            role=Role.CENTER_HEAD,
            password="test-pass-1",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị hệ thống",
            role=Role.SYSTEM_ADMIN,
            password="test-pass-1",
        )

        cls.ky = KyBaoCao.objects.create(
            nam=2026,
            so_ky=11,
            trang_thai=TrangThaiKy.MO,
        )

        cls.project = DuAn.objects.create(
            phong=cls.htkn,
            ten_du_an="Startup A",
            chuong_trinh="nq20",
            hinh_thuc="uom_tao",
            nam=2026,
        )

    def make_activity(self, **overrides):
        values = {
            "loai_hoat_dong": self.loai_htkn,
            "ten": "Lớp khởi nghiệp tháng 11",
            "tu_ngay": date(2026, 11, 5),
            "den_ngay": date(2026, 11, 7),
            "trang_thai": TrangThaiHoatDong.DA_TO_CHUC,
        }
        values.update(overrides)
        return HoatDong.objects.create(**values)

    def make_ad_hoc(self):
        return self.make_activity(
            loai_hoat_dong=self.loai_ad_hoc,
            ten="Nhiệm vụ đột xuất",
            noi_dung="Hỗ trợ đột xuất",
            ket_qua="Hoàn thành",
        )

    def login(self, user):
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        return client

    def activity_url(self, activity):
        return f"/phieu/hoat-dong/{activity.pk}/"

    def monthly_url(self):
        return f"/phieu/thang/{self.ky.pk}/"

    def project_url(self):
        return f"/phieu/du-an/{self.project.pk}/"


class ActivityEntryTests(EntryFixtureMixin, TestCase):
    def test_get_creates_primary_phieu_and_shows_only_htkn_fields(self):
        activity = self.make_activity()
        response = self.login(self.cb_htkn).get(self.activity_url(activity))
        self.assertEqual(response.status_code, 200)
        phieu = PhieuNhapLieu.objects.get(
            hoat_dong=activity,
            la_phieu_bo_sung=False,
        )
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertEqual(phieu.nguoi_nhap, self.cb_htkn)
        form = response.context["form"]
        self.assertIn(f"gia_tri_{self.hv.pk}", form.fields)
        self.assertIn(f"gia_tri_{self.cn.pk}", form.fields)
        self.assertIn(f"gia_tri_{self.cg.pk}", form.fields)
        self.assertIn(f"gia_tri_{self.ks.pk}", form.fields)
        self.assertNotIn(f"gia_tri_{self.gdcn_indicator.pk}", form.fields)
        self.assertContains(response, "Đã tổ chức/tổng số")
        self.assertContains(response, "Số hoạt động đã tổ chức")

    def test_saving_one_value_creates_exactly_one_row(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        response = client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        self.assertEqual(response.status_code, 302)
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        rows = SoLieu.objects.filter(phieu=phieu, chi_tieu=self.hv)
        self.assertEqual(rows.count(), 1)
        self.assertEqual(rows.get().gia_tri, Decimal("20"))

    def test_planned_activity_does_not_create_a_phieu(self):
        activity = self.make_activity(
            trang_thai=TrangThaiHoatDong.KE_HOACH
        )
        response = self.login(self.cb_htkn).get(self.activity_url(activity))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chưa được tổ chức")
        self.assertFalse(
            PhieuNhapLieu.objects.filter(hoat_dong=activity).exists()
        )

    def test_cross_department_activity_is_not_found(self):
        activity = self.make_activity()
        client = self.login(self.cb_gdcn)
        response = client.get(self.activity_url(activity))
        self.assertEqual(response.status_code, 404)
        response = client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        self.assertEqual(response.status_code, 404)

    def test_system_admin_cannot_post_activity_entry(self):
        activity = self.make_activity()
        response = self.login(self.admin).post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        self.assertEqual(response.status_code, 403)

    def test_center_head_is_read_only(self):
        activity = self.make_activity()
        client = self.login(self.center)
        response = client.get(self.activity_url(activity))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Lưu nháp")
        response = client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        self.assertEqual(response.status_code, 403)

    def test_center_head_get_does_not_create_a_phieu(self):
        activity = self.make_activity()
        response = self.login(self.center).get(self.activity_url(activity))
        self.assertEqual(response.status_code, 200)
        self.assertFalse(
            PhieuNhapLieu.objects.filter(hoat_dong=activity).exists()
        )

    def test_source_outside_allowed_set_is_rejected(self):
        activity = self.make_activity()
        form = ActivityEntryForm(
            data={
                f"gia_tri_{self.hv.pk}": "20",
                f"nguon_{self.hv.pk}": self.nguon_event.pk,
            },
            activity=activity,
        )
        self.assertFalse(form.is_valid())
        self.assertIn(f"nguon_{self.hv.pk}", form.errors)

    def test_required_rows_are_not_enforced_on_draft_save(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        response = client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        self.assertEqual(response.status_code, 302)
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)

    def test_validate_required_reports_missing_required_rows(self):
        activity = self.make_activity()
        phieu = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            nguoi_nhap=self.cb_htkn,
        )
        form = ActivityEntryForm(data={}, activity=activity, phieu=phieu)
        self.assertTrue(form.is_valid())
        with self.assertRaises(ValidationError) as caught:
            form.validate_required()
        self.assertIn(f"gia_tri_{self.hv.pk}", caught.exception.message_dict)

        form = ActivityEntryForm(
            data={
                f"gia_tri_{self.hv.pk}": "20",
                f"gia_tri_{self.cn.pk}": "10",
                f"gia_tri_{self.cg.pk}": "2",
                f"gia_tri_{self.ks.pk}": "5",
            },
            activity=activity,
            phieu=phieu,
        )
        self.assertTrue(form.is_valid())
        form.validate_required()


class CrossFieldValidationTests(EntryFixtureMixin, TestCase):
    def test_certificate_count_may_not_exceed_trainees(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        response = client.post(
            self.activity_url(activity),
            {
                f"gia_tri_{self.hv.pk}": "20",
                f"gia_tri_{self.cn.pk}": "30",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "vượt quá")

        response = client.post(
            self.activity_url(activity),
            {
                f"gia_tri_{self.hv.pk}": "20",
                f"gia_tri_{self.cn.pk}": "10",
            },
        )
        self.assertEqual(response.status_code, 302)

    def test_negative_value_is_rejected(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        response = client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "-1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "không được âm")

    def test_split_mismatch_reports_difference_and_valid_splits_save(self):
        client = self.login(self.cb_tttk)
        client.get(self.monthly_url())
        data = {
            f"gia_tri_{self.ndt.pk}": "30",
            f"doi_tuong_{self.ndt.pk}_{self.obj_dn.pk}": "10",
            f"doi_tuong_{self.ndt.pk}_{self.obj_sv.pk}": "10",
            f"linh_vuc_{self.ndt.pk}": [
                str(self.lv_qd36.pk),
                str(self.lv_qd36b.pk),
                str(self.lv_tt24.pk),
                str(self.lv_tt24b.pk),
            ],
            f"gia_tri_lv_{self.ndt.pk}": ["10", "10", "10", "10"],
        }
        response = client.post(self.monthly_url(), data)
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "lệch")

        data[f"gia_tri_{self.ndt.pk}"] = "20"
        response = client.post(self.monthly_url(), data)
        self.assertEqual(response.status_code, 302)
        phieu = PhieuNhapLieu.objects.get(
            phong=self.tttk,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
        )
        rows = SoLieu.objects.filter(phieu=phieu, chi_tieu=self.ndt)
        self.assertEqual(rows.count(), 7)
        total = rows.get(doi_tuong__isnull=True, linh_vuc__isnull=True)
        self.assertEqual(total.gia_tri, Decimal("20"))
        self.assertEqual(rows.filter(doi_tuong__isnull=False).count(), 2)
        self.assertEqual(rows.filter(linh_vuc__isnull=False).count(), 4)

    def test_solieu_row_cannot_carry_both_splits(self):
        phieu = PhieuNhapLieu.objects.create(
            phong=self.tttk,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
            nguoi_nhap=self.cb_tttk,
        )
        row = SoLieu(
            phieu=phieu,
            chi_tieu=self.ndt,
            gia_tri=Decimal("1"),
            doi_tuong=self.obj_dn,
            linh_vuc=self.lv_qd36,
        )
        with self.assertRaises(ValidationError):
            row.save()

    def test_field_row_without_value_is_rejected(self):
        client = self.login(self.cb_tttk)
        client.get(self.monthly_url())
        response = client.post(
            self.monthly_url(),
            {
                f"gia_tri_{self.ndt.pk}": "10",
                f"linh_vuc_{self.ndt.pk}": [str(self.lv_qd36.pk)],
                f"gia_tri_lv_{self.ndt.pk}": [""],
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nhập giá trị cho lĩnh vực đã chọn")


class DraftAndDeleteTests(EntryFixtureMixin, TestCase):
    def test_draft_save_keeps_status_and_delete_removes_rows(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        client.post(
            self.activity_url(activity),
            {f"gia_tri_{self.hv.pk}": "20"},
        )
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
        self.assertTrue(SoLieu.objects.filter(phieu=phieu).exists())

        response = client.post(f"/phieu/{phieu.pk}/xoa/")
        self.assertEqual(response.status_code, 302)
        self.assertFalse(PhieuNhapLieu.objects.filter(pk=phieu.pk).exists())
        self.assertFalse(SoLieu.objects.filter(phieu_id=phieu.pk).exists())

    def test_center_head_cannot_delete(self):
        activity = self.make_activity()
        self.login(self.cb_htkn).get(self.activity_url(activity))
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        response = self.login(self.center).post(f"/phieu/{phieu.pk}/xoa/")
        self.assertEqual(response.status_code, 403)

    def test_approved_phieu_cannot_be_deleted(self):
        activity = self.make_activity()
        self.login(self.cb_htkn).get(self.activity_url(activity))
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        phieu.trang_thai = TrangThaiPhieu.DA_DUYET
        phieu.save()
        response = self.login(self.cb_htkn).post(f"/phieu/{phieu.pk}/xoa/")
        self.assertEqual(response.status_code, 403)


class SupplementalPhieuTests(EntryFixtureMixin, TestCase):
    def test_supplemental_phieu_is_separate_and_defaults_to_survey_source(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        primary = PhieuNhapLieu.objects.get(hoat_dong=activity)

        response = client.post(
            f"/phieu/hoat-dong/{activity.pk}/bo-sung/"
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            PhieuNhapLieu.objects.filter(hoat_dong=activity).count(),
            2,
        )
        supplemental = PhieuNhapLieu.objects.get(
            hoat_dong=activity,
            la_phieu_bo_sung=True,
        )
        self.assertNotEqual(primary.pk, supplemental.pk)

        response = client.get(response.url)
        self.assertEqual(response.status_code, 200)
        form = response.context["form"]
        self.assertEqual(
            form.fields[f"nguon_{self.hv.pk}"].initial,
            self.nguon_survey.pk,
        )

    def test_center_head_cannot_create_supplemental(self):
        activity = self.make_activity()
        response = self.login(self.center).post(
            f"/phieu/hoat-dong/{activity.pk}/bo-sung/"
        )
        self.assertEqual(response.status_code, 403)

    def test_supplemental_save_does_not_mutate_primary(self):
        activity = self.make_activity()
        client = self.login(self.cb_htkn)
        client.get(self.activity_url(activity))
        primary = PhieuNhapLieu.objects.get(hoat_dong=activity)
        response = client.post(
            f"/phieu/hoat-dong/{activity.pk}/bo-sung/"
        )
        supplemental = PhieuNhapLieu.objects.get(
            hoat_dong=activity,
            la_phieu_bo_sung=True,
        )
        response = client.post(
            response.url,
            {f"gia_tri_{self.hv.pk}": "7"},
        )
        self.assertEqual(response.status_code, 302)
        self.assertFalse(SoLieu.objects.filter(phieu=primary).exists())
        self.assertEqual(
            SoLieu.objects.get(phieu=supplemental, chi_tieu=self.hv).gia_tri,
            Decimal("7"),
        )

    def test_supplemental_is_refused_for_ad_hoc(self):
        activity = self.make_ad_hoc()
        response = self.login(self.cb_htkn).post(
            f"/phieu/hoat-dong/{activity.pk}/bo-sung/"
        )
        self.assertEqual(response.status_code, 403)


class MonthlyEntryTests(EntryFixtureMixin, TestCase):
    def test_open_period_creates_and_saves_monthly_phieu(self):
        client = self.login(self.cb_tttk)
        response = client.get(self.monthly_url())
        self.assertEqual(response.status_code, 200)
        phieu = PhieuNhapLieu.objects.get(
            phong=self.tttk,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
        )
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)

        response = client.post(
            self.monthly_url(),
            {f"gia_tri_{self.ndt.pk}": "120"},
        )
        self.assertEqual(response.status_code, 302)
        row = SoLieu.objects.get(phieu=phieu, chi_tieu=self.ndt)
        self.assertEqual(row.gia_tri, Decimal("120"))

    def test_closed_period_is_read_only_and_refuses_post(self):
        client = self.login(self.cb_tttk)
        client.get(self.monthly_url())
        self.ky.trang_thai = TrangThaiKy.KHOA
        self.ky.save()
        response = client.get(self.monthly_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kỳ đã đóng")
        self.assertNotContains(response, "Lưu nháp")
        response = client.post(
            self.monthly_url(),
            {f"gia_tri_{self.ndt.pk}": "120"},
        )
        self.assertEqual(response.status_code, 403)

    def test_center_head_can_view_department_month_read_only(self):
        client = self.login(self.center)
        response = client.get(f"{self.monthly_url()}?phong={self.tttk.pk}")
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chế độ chỉ đọc")
        response = client.post(
            f"{self.monthly_url()}?phong={self.tttk.pk}",
            {f"gia_tri_{self.ndt.pk}": "120"},
        )
        self.assertEqual(response.status_code, 403)

    def test_monthly_phieu_is_department_scoped(self):
        self.login(self.cb_tttk).get(self.monthly_url())
        client = self.login(self.cb_gdcn)
        response = client.get(self.monthly_url())
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["phieu"].phong, self.gdcn)


class ProjectSupportTests(EntryFixtureMixin, TestCase):
    def test_entry_officer_adds_support_line(self):
        client = self.login(self.cb_htkn)
        response = client.get(self.project_url())
        self.assertEqual(response.status_code, 200)
        phieu = PhieuNhapLieu.objects.get(
            du_an=self.project,
            loai_phieu=LoaiPhieu.DU_AN,
        )
        response = client.post(
            self.project_url(),
            {
                "loai_ho_tro": "chuyen_gia",
                "noi_dung": "Tư vấn gọi vốn",
                "so_chuyen_gia": "2",
                "ngay_ho_tro": "2026-11-12",
            },
        )
        self.assertEqual(response.status_code, 302)
        line = HoTroDuAn.objects.get(phieu=phieu, du_an=self.project)
        self.assertEqual(line.so_chuyen_gia, Decimal("2"))
        self.assertEqual(line.ngay_ho_tro, date(2026, 11, 12))

    def test_negative_expert_count_and_missing_date_are_rejected(self):
        client = self.login(self.cb_htkn)
        client.get(self.project_url())
        response = client.post(
            self.project_url(),
            {
                "loai_ho_tro": "chuyen_gia",
                "noi_dung": "Tư vấn",
                "so_chuyen_gia": "-1",
                "ngay_ho_tro": "2026-11-12",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "không được âm")

        response = client.post(
            self.project_url(),
            {
                "loai_ho_tro": "chuyen_gia",
                "noi_dung": "Tư vấn",
                "so_chuyen_gia": "2",
                "ngay_ho_tro": "",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Nhập ngày hỗ trợ")

    def test_center_head_is_read_only(self):
        client = self.login(self.center)
        response = client.get(self.project_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "chế độ chỉ đọc")
        response = client.post(
            self.project_url(),
            {
                "loai_ho_tro": "chuyen_gia",
                "noi_dung": "Tư vấn",
                "so_chuyen_gia": "2",
                "ngay_ho_tro": "2026-11-12",
            },
        )
        self.assertEqual(response.status_code, 403)


class AdHocEntryTests(EntryFixtureMixin, TestCase):
    def test_ad_hoc_phieu_creates_no_solieu_and_saves_text(self):
        activity = self.make_ad_hoc()
        client = self.login(self.cb_htkn)
        response = client.get(self.activity_url(activity))
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["ad_hoc"])
        phieu = PhieuNhapLieu.objects.get(hoat_dong=activity)
        self.assertFalse(SoLieu.objects.filter(phieu=phieu).exists())

        response = client.post(
            self.activity_url(activity),
            {
                "noi_dung": "Nội dung đã cập nhật",
                "ket_qua": "Kết quả đã cập nhật",
            },
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(
            SoLieu.objects.filter(phieu=phieu).count(),
            0,
        )
        activity.refresh_from_db()
        self.assertEqual(activity.noi_dung, "Nội dung đã cập nhật")
        self.assertEqual(activity.ket_qua, "Kết quả đã cập nhật")
        self.assertEqual(phieu.trang_thai, TrangThaiPhieu.NHAP)
