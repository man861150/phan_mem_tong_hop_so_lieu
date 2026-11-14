"""Administration portal: grouping, dashboard, and preserved actions."""

import re

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib import admin
from django.template.loader import render_to_string
from django.test import RequestFactory, TestCase
from django.urls import reverse
from django.utils import timezone

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import DonViPhoiHop
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    KieuGhiNhan,
    KyBaoCao,
    NhomChiTieu,
    PhongBan,
    TrangThaiKy,
)
from apps.entry.models import LichSuXuLy, PhieuNhapLieu
from apps.reporting.models import BaoCaoDaXuat


class AdminPortalTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.phong = PhongBan.objects.create(ma_phong="HTKN", ten_phong="Phòng HTKN")
        PhongBan.objects.create(
            ma_phong="OLD",
            ten_phong="Phòng ngừng",
            dang_su_dung=False,
        )
        nhom = NhomChiTieu.objects.create(phong=cls.phong, ten_mang="Mảng", thu_tu=1)
        ChiTieu.objects.create(
            ma_chi_tieu="A1",
            ten_chi_tieu="Chỉ tiêu đang dùng",
            don_vi_tinh="Lượt",
            nhom=nhom,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
            cach_tong_hop=CachTongHop.SUM,
        )
        ChiTieu.objects.create(
            ma_chi_tieu="A2",
            ten_chi_tieu="Chỉ tiêu ngừng",
            don_vi_tinh="Lượt",
            nhom=nhom,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
            cach_tong_hop=CachTongHop.SUM,
            dang_su_dung=False,
        )
        year = timezone.localdate().year
        KyBaoCao.objects.create(nam=year, so_ky=1, trang_thai=TrangThaiKy.MO)
        KyBaoCao.objects.create(nam=year, so_ky=2, trang_thai=TrangThaiKy.KHOA)
        KyBaoCao.objects.create(nam=year - 1, so_ky=1, trang_thai=TrangThaiKy.MO)
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị viên",
            email="admin@example.com",
            role=Role.SYSTEM_ADMIN,
            password="mat-khau-cu-1",
            is_staff=True,
            is_superuser=True,
        )
        cls.officer = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Cán bộ",
            email="cb@example.com",
            role=Role.ENTRY_OFFICER,
            phong=cls.phong,
            password="mat-khau-cu-1",
        )
        User.objects.create_user(
            username="ld.htkn",
            ho_ten="Lãnh đạo phòng",
            email="ld@example.com",
            role=Role.DEPARTMENT_HEAD,
            phong=cls.phong,
            password="mat-khau-cu-1",
        )
        User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo Trung tâm",
            email="tt@example.com",
            role=Role.CENTER_HEAD,
            password="mat-khau-cu-1",
        )
        User.objects.create_user(
            username="ngung",
            ho_ten="Đã nghỉ",
            email="ngung@example.com",
            role=Role.ENTRY_OFFICER,
            phong=cls.phong,
            password="mat-khau-cu-1",
            is_active=False,
        )

    def setUp(self):
        self.client.force_login(self.admin)

    def test_dashboard_groups_models_and_shows_kpis(self):
        response = self.client.get(reverse("admin:index"))
        self.assertEqual(response.status_code, 200)
        body = response.content.decode()
        titles = [
            "Quản lý người dùng &amp; Phân quyền",
            "Kỳ báo cáo &amp; Kế hoạch năm",
            "Cấu hình Danh mục &amp; Chỉ tiêu",
            "Danh mục dùng chung",
            "Tra cứu &amp; Kiểm tra dữ liệu nghiệp vụ",
        ]
        headings = [
            match.strip()
            for match in re.findall(
                r'class="portal-domain-head".*?<h2>\s*([^<]+)',
                body,
                flags=re.S,
            )
        ]
        self.assertEqual(headings, titles)
        self.assertIn("Chỉ xem / Tra cứu đối soát", body)
        self.assertIn("Tài khoản bị khóa tạm", body)
        self.assertIn("Lĩnh vực", body)
        self.assertIn("Thêm người dùng", body)
        self.assertIn(reverse("admin:accounts_user_add"), body)
        self.assertIn("Mở / Khóa kỳ báo cáo", body)
        self.assertIn("Cập nhật kế hoạch năm", body)
        self.assertIn("Gộp đơn vị phối hợp trùng", body)
        self.assertIn("Về trang chính", body)
        self.assertRegex(body, r"Chào buổi (sáng|chiều|tối), Quản trị viên\.")
        self.assertIn('data-kpi="users-total">4<', body)
        self.assertIn('data-kpi="users-system-admin">Quản trị hệ thống: 1<', body)
        self.assertIn('data-kpi="users-center-head">Lãnh đạo Trung tâm: 1<', body)
        self.assertIn('data-kpi="users-department-head">Lãnh đạo phòng: 1<', body)
        self.assertIn('data-kpi="users-entry-officer">Cán bộ nhập liệu: 1<', body)
        self.assertIn(
            'data-kpi="periods-open"><span class="kpi-num">1</span> đang mở',
            body,
        )
        self.assertIn('data-kpi="periods-locked">1 đã khóa<', body)
        self.assertIn('data-kpi="departments">1<', body)
        self.assertIn('data-kpi="indicators">1<', body)
        self.assertNotIn("/admin/auth/group/", body)
        self.assertNotIn("access log", body.lower())
        self.assertNotIn("Có tài khoản đang bị khóa vì đăng nhập sai.", body)

    def test_lockout_banner_clears_after_unlock_action(self):
        AccessAttempt.objects.create(
            user_agent="test",
            ip_address="127.0.0.1",
            username=self.officer.username,
            http_accept="text/html",
            path_info="/dang-nhap/",
            get_data="",
            post_data="",
            failures_since_start=settings.AXES_FAILURE_LIMIT,
        )
        locked = self.client.get(reverse("admin:index"))
        self.assertContains(locked, "Có tài khoản đang bị khóa vì đăng nhập sai.")

        self.client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "mo_khoa_tai_khoan",
                "_selected_action": [str(self.officer.pk)],
            },
        )
        self.assertFalse(
            AccessAttempt.objects.filter(username=self.officer.username).exists()
        )
        cleared = self.client.get(reverse("admin:index"))
        self.assertNotContains(
            cleared,
            "Có tài khoản đang bị khóa vì đăng nhập sai.",
        )

    def test_empty_app_list_shows_the_permission_message(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        html = render_to_string(
            "admin/index.html",
            {
                "app_list": [],
                "portal_kpis": {
                    "year": 2026,
                    "users": {
                        "total": 0,
                        "system_admin": 0,
                        "center_head": 0,
                        "department_head": 0,
                        "entry_officer": 0,
                    },
                    "periods": {"mo": 0, "khoa": 0},
                    "departments": 0,
                    "indicators": 0,
                },
                "portal_greeting": "Chào buổi sáng",
                "portal_full_name": "Quản trị viên",
                "portal_email": "admin@example.com",
                "portal_initials": "QT",
                "portal_role_label": "Quản trị hệ thống",
                "lockout": {"count": 0, "url": "/admin/axes/accessattempt/"},
                "title": "Trung tâm điều hành",
            },
            request=request,
        )
        self.assertIn("Bạn không có quyền xem hoặc chỉnh sửa bất cứ gì.", html)
        self.assertNotIn('class="portal-domain', html)
        self.assertIn("Tổng quan", html)
        self.assertIn('data-kpi="users-total">0<', html)

    def test_other_roles_are_sent_to_the_admin_login(self):
        for username in ("cb.htkn", "ld.htkn", "ld.tt"):
            self.client.force_login(User.objects.get(username=username))
            response = self.client.get(reverse("admin:index"))
            self.assertEqual(response.status_code, 302, username)
            self.assertIn("/admin/login/", response["Location"])

    def test_read_only_models_and_custom_actions_stay(self):
        request = RequestFactory().get("/admin/")
        request.user = self.admin
        self.assertFalse(admin.site._registry[LichSuXuLy].has_add_permission(None))
        self.assertFalse(admin.site._registry[LichSuXuLy].has_change_permission(None))
        self.assertFalse(admin.site._registry[LichSuXuLy].has_delete_permission(None))
        self.assertFalse(admin.site._registry[PhieuNhapLieu].has_add_permission(None))
        self.assertFalse(
            admin.site._registry[PhieuNhapLieu].has_change_permission(None)
        )
        self.assertFalse(
            admin.site._registry[PhieuNhapLieu].has_delete_permission(None)
        )
        bao_cao = admin.site._registry[BaoCaoDaXuat]
        self.assertFalse(bao_cao.has_add_permission(None))
        self.assertFalse(bao_cao.has_change_permission(None))
        self.assertFalse(bao_cao.has_delete_permission(None))
        ky_actions = admin.site._registry[KyBaoCao].get_actions(request)
        self.assertIn("mo_ky", ky_actions)
        self.assertIn("khoa_ky", ky_actions)
        don_vi_actions = admin.site._registry[DonViPhoiHop].get_actions(request)
        self.assertIn("gop_don_vi_trung", don_vi_actions)
        reverse("admin:catalog_danhmuc_linh_vuc_load")

    def test_user_changelist_explains_search(self):
        response = self.client.get(reverse("admin:accounts_user_changelist"))
        self.assertContains(response, "Tìm theo tên đăng nhập, họ tên hoặc email.")
        self.assertContains(response, "← Về trang chính")
