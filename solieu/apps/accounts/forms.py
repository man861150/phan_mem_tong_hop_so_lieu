"""Users, roles, and department scope."""

from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    UserChangeForm,
)

from apps.accounts.models import User
from apps.accounts.roles import SCOPED_ROLE_DEPARTMENT_ERROR, SCOPED_ROLES


class DepartmentRequiredMixin:
    """Reject a scoped role that has no department. The model repeats this rule."""

    def clean(self):
        cleaned = super().clean()
        role = cleaned.get("role")
        phong = cleaned.get("phong")
        if role in SCOPED_ROLES and phong is None:
            self.add_error("phong", SCOPED_ROLE_DEPARTMENT_ERROR)
        return cleaned

    def _post_clean(self):
        super()._post_clean()
        errors = self.errors.get("phong")
        if not errors:
            return
        unique = []
        for message in errors:
            if message not in unique:
                unique.append(message)
        if len(unique) != len(errors):
            self._errors["phong"] = self.error_class(unique)


class UserAdminCreationForm(DepartmentRequiredMixin, AdminUserCreationForm):
    class Meta(AdminUserCreationForm.Meta):
        model = User
        fields = ("username", "ho_ten", "email", "role", "phong", "is_active")


class UserAdminChangeForm(DepartmentRequiredMixin, UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = User
        fields = (
            "username",
            "password",
            "ho_ten",
            "email",
            "role",
            "phong",
            "is_active",
        )


class LoginForm(AuthenticationForm):
    error_messages = {
        **AuthenticationForm.error_messages,
        "invalid_login": "Tên đăng nhập hoặc mật khẩu không đúng.",
        "inactive": "Tài khoản này đang bị khóa.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["username"].label = "Tên đăng nhập"
        self.fields["password"].label = "Mật khẩu"
