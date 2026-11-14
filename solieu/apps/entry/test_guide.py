"""Guided workflow page: roles, department scope, and real phiếu state."""

from datetime import date
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import (
    ChuongTrinhDuAn,
    DuAn,
    HinhThucDuAn,
    HoatDong,
    TrangThaiHoatDong,
)
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    KieuGhiNhan,
    KyBaoCao,
    LoaiHoatDong,
    LoaiHoTro,
    NhomChiTieu,
    PhongBan,
    TrangThaiKy,
)
from apps.entry.guide import ROW_LIMIT
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LichSuXuLy,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)


class GuideFixture:
    @classmethod
    def setUpTestData(cls):
        cls.htkn = PhongBan.objects.create(ma_phong="HTKN", ten_phong="Phòng HTKN")
        cls.gdcn = PhongBan.objects.create(ma_phong="GDCN", ten_phong="Phòng GDCN")
        cls.officer = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Cán bộ HTKN",
            email="cb@example.com",
            role=Role.ENTRY_OFFICER,
            phong=cls.htkn,
            password="mat-khau-1",
        )
        cls.head = User.objects.create_user(
            username="ld.htkn",
            ho_ten="Lãnh đạo HTKN",
            email="ld@example.com",
            role=Role.DEPARTMENT_HEAD,
            phong=cls.htkn,
            password="mat-khau-1",
        )
        cls.center = User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo trung tâm",
            email="tt@example.com",
            role=Role.CENTER_HEAD,
            password="mat-khau-1",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị",
            email="admin@example.com",
            role=Role.SYSTEM_ADMIN,
            password="mat-khau-1",
            is_staff=True,
        )
        cls.loai = LoaiHoatDong.objects.create(
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
        cls.nhom = NhomChiTieu.objects.create(phong=cls.htkn, ten_mang="HTKN")
        cls.chi_tieu = ChiTieu.objects.create(
            ma_chi_tieu="HTKN-SUM",
            ten_chi_tieu="Số lượt",
            don_vi_tinh="lượt",
            nhom=cls.nhom,
            kieu_ghi_nhan=KieuGhiNhan.ACTIVITY,
            cach_tong_hop=CachTongHop.SUM,
        )

    def guide(self, user):
        self.client.force_login(user)
        return self.client.get(reverse("entry:quy_trinh"))

    def workflow(self, response, key):
        return next(
            item
            for item in response.context["workflows"]
            if item["key"] == key
        )

    def activity(self, ten, *, loai=None, trang_thai=TrangThaiHoatDong.KE_HOACH):
        return HoatDong.objects.create(
            loai_hoat_dong=loai or self.loai,
            ten=ten,
            tu_ngay=date(2026, 11, 1),
            trang_thai=trang_thai,
        )

    def phieu(self, **kwargs):
        kwargs.setdefault("phong", self.htkn)
        kwargs.setdefault("nguoi_nhap", self.officer)
        kwargs.setdefault("trang_thai", TrangThaiPhieu.NHAP)
        return PhieuNhapLieu.objects.create(**kwargs)

    def project(self, ten, *, phong=None):
        return DuAn.objects.create(
            phong=phong or self.htkn,
            ten_du_an=ten,
            chuong_trinh=ChuongTrinhDuAn.NQ20,
            hinh_thuc=HinhThucDuAn.UOM_TAO,
            nam=2026,
        )


class GuideAccessTests(GuideFixture, TestCase):
    def test_anonymous_user_is_sent_to_login(self):
        response = self.client.get(reverse("entry:quy_trinh"))

        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response.url)

    def test_center_head_and_admin_are_refused(self):
        for user in (self.center, self.admin):
            response = self.guide(user)
            self.assertEqual(response.status_code, 403)

    def test_entry_officer_sees_three_workflows_and_not_approval(self):
        response = self.guide(self.officer)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Kết quả hoạt động")
        self.assertContains(response, "Phiếu tháng")
        self.assertContains(response, "Hỗ trợ dự án")
        self.assertContains(response, "Tạo hoạt động")
        self.assertContains(response, "Thêm dự án")
        self.assertNotContains(response, "Mở danh sách chờ duyệt")
        self.assertNotContains(response, "Xem và duyệt")
        self.assertNotContains(response, reverse("entry:duyet_list"))
        self.assertContains(response, "Trang chủ")
        self.assertContains(response, "Hoạt động")
        self.assertContains(response, "Dự án")
        self.assertContains(response, "Quy trình")
        main = response.content.decode().split("<main", 1)[1].split("</main>", 1)[0]
        self.assertNotIn("<form", main)

    def test_sidebar_hides_the_guide_from_other_roles(self):
        self.client.force_login(self.admin)
        response = self.client.get(reverse("accounts:profile"))

        self.assertNotContains(response, "Quy trình")

        self.client.force_login(self.center)
        listed = self.client.get(reverse("activities:hoat_dong_list"))

        self.assertNotContains(listed, "Quy trình công việc")

    def test_department_head_sees_the_approval_queue(self):
        activity = self.activity(
            "Lớp chờ duyệt",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        self.phieu(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )
        other = self.activity(
            "Việc phòng khác",
            loai=self.loai_gdcn,
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        self.phieu(
            phong=self.gdcn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=other,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )

        response = self.guide(self.head)
        activity_flow = self.workflow(response, "hoat_dong")

        self.assertContains(response, "Mở danh sách chờ duyệt")
        self.assertContains(response, "1 phiếu trong phòng đang chờ duyệt")
        self.assertContains(response, "Xem và duyệt")
        self.assertNotContains(response, "Việc phòng khác")
        self.assertEqual(activity_flow["items"][0]["action_label"], "Xem và duyệt")
        self.assertEqual(
            activity_flow["items"][0]["action_url"],
            reverse("entry:phieu_detail", args=[activity.phieu_nhap_lieu.get().pk]),
        )

    def test_other_department_records_stay_hidden(self):
        self.activity("Lớp của HTKN")
        self.activity("Sự kiện GDCN", loai=self.loai_gdcn)
        self.project("Dự án HTKN")
        self.project("Dự án GDCN", phong=self.gdcn)
        KyBaoCao.objects.create(nam=2019, so_ky=2, trang_thai=TrangThaiKy.KHOA)
        self.phieu(
            phong=self.gdcn,
            loai_phieu=LoaiPhieu.THANG,
            ky=KyBaoCao.objects.get(nam=2019, so_ky=2),
        )

        response = self.guide(self.officer)

        self.assertContains(response, "Lớp của HTKN")
        self.assertContains(response, "Dự án HTKN")
        self.assertNotContains(response, "Sự kiện GDCN")
        self.assertNotContains(response, "Dự án GDCN")
        self.assertNotContains(response, "Tháng 2/2019")


class GuideOverviewTests(GuideFixture, TestCase):
    def test_summary_counts_are_scoped_to_the_department(self):
        self.phieu(
            loai_phieu=LoaiPhieu.THANG,
            ky=KyBaoCao.objects.create(
                nam=2026,
                so_ky=11,
                trang_thai=TrangThaiKy.MO,
            ),
        )
        self.phieu(
            loai_phieu=LoaiPhieu.THANG,
            ky=KyBaoCao.objects.create(
                nam=2026,
                so_ky=10,
                trang_thai=TrangThaiKy.KHOA,
            ),
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )
        self.phieu(
            loai_phieu=LoaiPhieu.THANG,
            ky=KyBaoCao.objects.create(
                nam=2026,
                so_ky=9,
                trang_thai=TrangThaiKy.KHOA,
            ),
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        other_ky = KyBaoCao.objects.create(
            nam=2026,
            so_ky=8,
            trang_thai=TrangThaiKy.KHOA,
        )
        self.phieu(
            phong=self.gdcn,
            loai_phieu=LoaiPhieu.THANG,
            ky=other_ky,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )

        response = self.guide(self.officer)

        self.assertEqual(
            response.context["summary"],
            {"in_progress": 1, "pending": 1, "completed": 1},
        )
        self.assertContains(response, "Đang xử lý")
        self.assertContains(response, "Chờ duyệt")
        self.assertContains(response, "Hoàn thành")

    def test_step_badge_and_stepper_state_follow_the_first_open_item(self):
        self.activity("Lớp kế hoạch")
        workflow = self.workflow(self.guide(self.officer), "hoat_dong")

        self.assertEqual(workflow["step_badge"], "Bước 2/6")
        self.assertEqual(workflow["steps"][1]["state"], "current")
        self.assertEqual(workflow["items"][0]["state_pill_label"], "Đang làm")

    def test_waiting_project_shows_a_status_badge_only_when_read_only(self):
        project = self.project("Dự án chờ duyệt")
        self.phieu(
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=project,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )

        officer = self.workflow(self.guide(self.officer), "du_an")
        self.assertEqual(officer["status_badge"], "Chờ phản hồi")
        self.assertEqual(
            officer["items"][0]["state_pill_label"], "Không thể thực hiện"
        )

        head = self.workflow(self.guide(self.head), "du_an")
        self.assertEqual(head["status_badge"], "")
        self.assertEqual(head["step_badge"], "Bước 5/5")


class GuideActivityTests(GuideFixture, TestCase):
    def test_planned_activity_links_to_the_detail_page(self):
        activity = self.activity("Lớp kế hoạch")

        response = self.guide(self.officer)
        item = self.workflow(response, "hoat_dong")["items"][0]

        self.assertEqual(item["step_number"], 2)
        self.assertEqual(item["action_label"], "Mở hoạt động để chuyển trạng thái")
        self.assertEqual(
            item["action_url"],
            reverse("activities:hoat_dong_detail", args=[activity.pk]),
        )
        self.assertNotContains(response, "da-to-chuc")

    def test_organized_activity_without_a_phieu_links_to_the_form(self):
        activity = self.activity(
            "Lớp đã tổ chức",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        before = PhieuNhapLieu.objects.count()

        response = self.guide(self.officer)
        item = self.workflow(response, "hoat_dong")["items"][0]

        self.assertEqual(PhieuNhapLieu.objects.count(), before)
        self.assertEqual(item["action_label"], "Mở phiếu kết quả")
        self.assertEqual(
            item["action_url"],
            reverse("entry:phieu_hoat_dong", args=[activity.pk]),
        )

    def test_draft_with_values_asks_the_user_to_submit_on_the_form(self):
        activity = self.activity(
            "Lớp đã nhập",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        phieu = self.phieu(loai_phieu=LoaiPhieu.HOAT_DONG, hoat_dong=activity)
        SoLieu.objects.create(phieu=phieu, chi_tieu=self.chi_tieu, gia_tri=Decimal("2"))

        item = self.workflow(self.guide(self.officer), "hoat_dong")["items"][0]

        self.assertEqual(item["step_number"], 5)
        self.assertEqual(item["action_label"], "Mở phiếu để gửi duyệt")
        self.assertIn("chỉ tiêu bắt buộc", item["explanation"])

    def test_returned_phieu_shows_the_comment_and_the_form(self):
        activity = self.activity(
            "Lớp bị trả",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        phieu = self.phieu(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            trang_thai=TrangThaiPhieu.TRA_LAI,
        )
        LichSuXuLy.objects.create(
            phieu=phieu,
            nguoi_xu_ly=self.head,
            hanh_dong=HanhDongXuLy.TRA_LAI,
            y_kien="Sai tổng học viên",
        )

        response = self.guide(self.officer)
        item = self.workflow(response, "hoat_dong")["items"][0]

        self.assertEqual(item["comment"], "Sai tổng học viên")
        self.assertEqual(item["action_label"], "Sửa và gửi lại")
        self.assertContains(response, "Sai tổng học viên")

    def test_waiting_phieu_is_view_only_for_the_officer(self):
        activity = self.activity(
            "Lớp chờ",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        phieu = self.phieu(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )

        response = self.guide(self.officer)
        item = self.workflow(response, "hoat_dong")["items"][0]

        self.assertEqual(item["state"], "blocked")
        self.assertEqual(item["action_label"], "Xem trạng thái")
        self.assertIn("chỉ được xem", item["explanation"])
        self.assertEqual(
            item["action_url"],
            reverse("entry:phieu_detail", args=[phieu.pk]),
        )

    def test_supplement_keeps_its_own_link(self):
        activity = self.activity(
            "Lớp bổ sung",
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        self.phieu(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        supplement = self.phieu(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            la_phieu_bo_sung=True,
            trang_thai=TrangThaiPhieu.NHAP,
        )

        flow = self.workflow(self.guide(self.officer), "hoat_dong")

        self.assertEqual(flow["completed_count"], 1)
        self.assertEqual(len(flow["items"]), 1)
        self.assertIn("Phiếu bổ sung", flow["items"][0]["meta"])
        self.assertIn(f"?phieu={supplement.pk}", flow["items"][0]["action_url"])

    def test_long_queue_keeps_a_real_remainder(self):
        for number in range(ROW_LIMIT + 1):
            self.activity(f"Lớp {number:02d}")

        flow = self.workflow(self.guide(self.officer), "hoat_dong")

        self.assertEqual(len(flow["items"]), ROW_LIMIT)
        self.assertEqual(flow["hidden_count"], 1)


class GuideMonthTests(GuideFixture, TestCase):
    def test_open_month_without_a_phieu_links_to_the_month_form(self):
        ky = KyBaoCao.objects.create(nam=2026, so_ky=11, trang_thai=TrangThaiKy.MO)
        before = PhieuNhapLieu.objects.count()

        response = self.guide(self.officer)
        item = self.workflow(response, "thang")["items"][0]

        self.assertEqual(PhieuNhapLieu.objects.count(), before)
        self.assertEqual(item["title"], "Tháng 11/2026")
        self.assertEqual(item["action_label"], "Nhập số liệu và lưu nháp")
        self.assertEqual(item["action_url"], reverse("entry:phieu_thang", args=[ky.pk]))

    def test_closed_month_cannot_be_edited(self):
        ky = KyBaoCao.objects.create(nam=2026, so_ky=10, trang_thai=TrangThaiKy.KHOA)
        self.phieu(loai_phieu=LoaiPhieu.THANG, ky=ky)

        response = self.guide(self.officer)
        item = self.workflow(response, "thang")["items"][0]

        self.assertEqual(item["state"], "blocked")
        self.assertEqual(item["action_label"], "Xem phiếu")
        self.assertIn("Kỳ đã đóng", item["explanation"])
        self.assertContains(response, "Kỳ đã đóng. Phiếu tháng chỉ được xem")

    def test_no_open_period_explains_why_entry_is_unavailable(self):
        KyBaoCao.objects.create(nam=2026, so_ky=9, trang_thai=TrangThaiKy.KHOA)

        flow = self.workflow(self.guide(self.officer), "thang")

        self.assertEqual(flow["items"], [])
        self.assertIn("Không có kỳ đang mở", flow["blocked_message"])
        self.assertEqual(flow["primary_url"], reverse("entry:phieu_thang_chon"))
        self.assertTrue(flow["steps"][0]["current"])
        self.assertEqual(flow["steps"][0]["state"], "blocked")

    def test_returned_open_month_links_back_to_the_form(self):
        ky = KyBaoCao.objects.create(nam=2026, so_ky=8, trang_thai=TrangThaiKy.MO)
        phieu = self.phieu(
            loai_phieu=LoaiPhieu.THANG,
            ky=ky,
            trang_thai=TrangThaiPhieu.TRA_LAI,
        )
        LichSuXuLy.objects.create(
            phieu=phieu,
            nguoi_xu_ly=self.head,
            hanh_dong=HanhDongXuLy.TRA_LAI,
            y_kien="Thiếu nguồn số liệu",
        )

        item = self.workflow(self.guide(self.officer), "thang")["items"][0]

        self.assertEqual(item["action_label"], "Sửa và gửi lại")
        self.assertEqual(item["comment"], "Thiếu nguồn số liệu")
        self.assertEqual(item["action_url"], reverse("entry:phieu_thang", args=[ky.pk]))


class GuideProjectTests(GuideFixture, TestCase):
    def test_project_without_lines_opens_the_support_form(self):
        project = self.project("Dự án trống")
        before = PhieuNhapLieu.objects.count()

        item = self.workflow(self.guide(self.officer), "du_an")["items"][0]

        self.assertEqual(PhieuNhapLieu.objects.count(), before)
        self.assertEqual(item["action_label"], "Mở phiếu hỗ trợ")
        self.assertEqual(
            item["action_url"],
            reverse("entry:phieu_du_an", args=[project.pk]),
        )

    def test_project_with_lines_is_ready_to_submit(self):
        project = self.project("Dự án có dòng")
        phieu = self.phieu(loai_phieu=LoaiPhieu.DU_AN, du_an=project)
        HoTroDuAn.objects.create(
            du_an=project,
            phieu=phieu,
            loai_ho_tro=LoaiHoTro.KHAC,
            noi_dung="Tư vấn",
            ngay_ho_tro=date(2026, 11, 2),
        )

        item = self.workflow(self.guide(self.officer), "du_an")["items"][0]

        self.assertEqual(item["step_number"], 4)
        self.assertEqual(item["action_label"], "Mở phiếu để gửi duyệt")
        self.assertIn("ít nhất một dòng", item["explanation"])

    def test_approved_project_is_counted_instead_of_listed(self):
        project = self.project("Dự án xong")
        self.phieu(
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=project,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )

        flow = self.workflow(self.guide(self.officer), "du_an")

        self.assertEqual(flow["items"], [])
        self.assertEqual(flow["completed_count"], 1)
        self.assertEqual(flow["primary_label"], "Thêm dự án")


class GuideReturnLinkTests(GuideFixture, TestCase):
    def test_entry_screens_link_back_to_the_guide(self):
        self.client.force_login(self.officer)
        response = self.client.get(reverse("entry:phieu_thang_chon"))

        self.assertContains(response, reverse("entry:quy_trinh"))
        self.assertContains(response, "Quy trình công việc")
