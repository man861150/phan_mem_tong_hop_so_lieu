"""Users, roles, and department scope."""

from django.test import Client, TestCase
from django.urls import reverse

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.catalog.models import PhongBan


class AccountFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        cls.phong = PhongBan.objects.create(
            ma_phong="HTKN",
            ten_phong="Phòng HTKN",
        )
        cls.user = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Nguyễn Văn An",
            email="an@example.com",
            role=Role.ENTRY_OFFICER,
            phong=cls.phong,
            password="mat-khau-cu-1",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị viên",
            email="admin@example.com",
            role=Role.SYSTEM_ADMIN,
            password="mat-khau-cu-1",
            is_staff=True,
            is_superuser=True,
        )

    def login(self, user=None):
        self.client.force_login(user or self.user)


class InitialsTests(TestCase):
    def test_uses_first_and_last_word(self):
        user = User(username="cb.htkn", ho_ten="  Nguyễn   Văn An ")
        self.assertEqual(user.initials, "NA")

    def test_single_word_uses_two_letters(self):
        user = User(username="cb", ho_ten="An")
        self.assertEqual(user.initials, "AN")

    def test_falls_back_to_username(self):
        user = User(username="cb.htkn", ho_ten="")
        self.assertEqual(user.initials, "CB")

    def test_falls_back_to_question_mark(self):
        user = User(username="", ho_ten="")
        self.assertEqual(user.initials, "?")


class AccountMenuTests(AccountFixtureMixin, TestCase):
    def test_header_lists_account_actions(self):
        self.login()
        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, 'aria-controls="account-menu-panel"')
        self.assertContains(response, "Thông tin tài khoản")
        self.assertContains(response, "Cài đặt")
        self.assertContains(response, "Đăng xuất")
        self.assertContains(response, "NA")

    def test_anonymous_user_has_no_account_menu(self):
        response = self.client.get(reverse("accounts:login"))

        self.assertNotContains(response, "account-menu-panel")
        self.assertNotContains(response, "Thông tin tài khoản")
        self.assertContains(response, "Hệ thống tổng hợp số liệu - v2.0")

    def test_sidebar_user_card_is_gone(self):
        self.login()
        response = self.client.get(reverse("accounts:profile"))

        self.assertNotContains(response, "sidebar-user")
        self.assertNotContains(response, "logout-button")

    def test_sidebar_keeps_role_navigation(self):
        self.login(self.admin)
        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, "Danh mục")
        self.assertContains(response, "Quản trị")


class ProfileTests(AccountFixtureMixin, TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_shows_current_account_information(self):
        self.login()
        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, "Nguyễn Văn An")
        self.assertContains(response, "cb.htkn")
        self.assertContains(response, "an@example.com")
        self.assertContains(response, "Cán bộ nhập liệu")
        self.assertContains(response, "Phòng HTKN")

    def test_shows_profile_sections_and_system_metadata(self):
        self.login()
        response = self.client.get(reverse("accounts:profile"))

        self.assertContains(response, "Chỉnh sửa thông tin")
        self.assertContains(response, "Thông tin hồ sơ")
        self.assertContains(response, "Thông tin hệ thống")
        self.assertContains(response, "Tài khoản đang hoạt động")
        self.assertContains(response, "Tên hiển thị")
        self.assertContains(response, "Địa chỉ email")
        self.assertContains(response, "Mã tài khoản")
        self.assertContains(response, "Ngày tham gia")
        self.assertContains(response, "Đăng nhập gần nhất")
        self.assertContains(response, "Phiên bản hệ thống")
        self.assertContains(response, "v2.0")
        self.assertContains(response, "Thông tin này do quản trị viên quản lý.")
        self.assertNotContains(response, "Người phụ trách")
        self.assertNotContains(response, "Số điện thoại")

    def test_updates_name_and_email(self):
        self.login()
        response = self.client.post(
            reverse("accounts:profile"),
            {"ho_ten": "Nguyễn Văn Bình", "email": "binh@example.com"},
            follow=True,
        )

        self.assertContains(response, "Đã cập nhật thông tin tài khoản.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ho_ten, "Nguyễn Văn Bình")
        self.assertEqual(self.user.email, "binh@example.com")

    def test_rejects_blank_name(self):
        self.login()
        response = self.client.post(
            reverse("accounts:profile"),
            {"ho_ten": "   ", "email": "an@example.com"},
        )

        self.assertContains(response, "Vui lòng nhập họ và tên.")
        self.assertContains(response, "editing: true")
        self.user.refresh_from_db()
        self.assertEqual(self.user.ho_ten, "Nguyễn Văn An")

    def test_rejects_invalid_email(self):
        self.login()
        response = self.client.post(
            reverse("accounts:profile"),
            {"ho_ten": "Nguyễn Văn An", "email": "khong-hop-le"},
        )

        self.assertContains(response, "Email không hợp lệ.")
        self.user.refresh_from_db()
        self.assertEqual(self.user.email, "an@example.com")

    def test_cannot_change_authorization_fields(self):
        self.login()
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "ho_ten": "Nguyễn Văn An",
                "email": "an@example.com",
                "username": "admin",
                "role": Role.SYSTEM_ADMIN,
                "phong": "",
                "is_staff": "on",
                "is_superuser": "on",
            },
        )

        self.assertEqual(response.status_code, 302)
        self.user.refresh_from_db()
        self.assertEqual(self.user.username, "cb.htkn")
        self.assertEqual(self.user.role, Role.ENTRY_OFFICER)
        self.assertEqual(self.user.phong, self.phong)
        self.assertFalse(self.user.is_staff)
        self.assertFalse(self.user.is_superuser)


class SettingsTests(AccountFixtureMixin, TestCase):
    def test_requires_login(self):
        response = self.client.get(reverse("accounts:settings"))

        self.assertEqual(response.status_code, 302)
        self.assertTrue(response.url.startswith(reverse("accounts:login")))

    def test_shows_password_form(self):
        self.login()
        response = self.client.get(reverse("accounts:settings"))

        self.assertContains(response, "Đổi mật khẩu")
        self.assertContains(response, "Mật khẩu hiện tại")
        self.assertContains(response, "Xác nhận mật khẩu mới")

    def test_rejects_wrong_current_password(self):
        self.login()
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "sai-mat-khau",
                "new_password1": "Mat-khau-moi-2026",
                "new_password2": "Mat-khau-moi-2026",
            },
        )

        self.assertContains(response, "Mật khẩu hiện tại không đúng.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("mat-khau-cu-1"))

    def test_rejects_mismatched_new_passwords(self):
        self.login()
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "mat-khau-cu-1",
                "new_password1": "Mat-khau-moi-2026",
                "new_password2": "Mat-khau-moi-2027",
            },
        )

        self.assertContains(response, "Hai mật khẩu mới không khớp.")

    def test_changes_password(self):
        self.login()
        response = self.client.post(
            reverse("accounts:settings"),
            {
                "old_password": "mat-khau-cu-1",
                "new_password1": "Mat-khau-moi-2026",
                "new_password2": "Mat-khau-moi-2026",
            },
            follow=True,
        )

        self.assertContains(response, "Đã đổi mật khẩu.")
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("Mat-khau-moi-2026"))


class LogoutTests(AccountFixtureMixin, TestCase):
    def test_get_cannot_log_out(self):
        self.login()
        response = self.client.get(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 405)
        self.assertIn("_auth_user_id", self.client.session)

    def test_post_ends_session_and_returns_to_login(self):
        self.login()
        response = self.client.post(reverse("accounts:logout"))

        self.assertRedirects(response, reverse("accounts:login"))
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_post_requires_csrf_token(self):
        client = Client(enforce_csrf_checks=True)
        client.force_login(self.user)

        response = client.post(reverse("accounts:logout"))

        self.assertEqual(response.status_code, 403)
        self.assertIn("_auth_user_id", client.session)
