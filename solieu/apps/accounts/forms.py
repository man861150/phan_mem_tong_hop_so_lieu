"""Users, roles, and department scope."""

from django import forms
from django.contrib.auth.forms import (
    AdminUserCreationForm,
    AuthenticationForm,
    PasswordChangeForm,
    UserChangeForm,
)
from django.contrib.auth.password_validation import (
    CommonPasswordValidator,
    MinimumLengthValidator,
    NumericPasswordValidator,
    UserAttributeSimilarityValidator,
    get_default_password_validators,
)

from apps.accounts.models import User
from apps.accounts.roles import SCOPED_ROLE_DEPARTMENT_ERROR, SCOPED_ROLES

RULE_ORDER = {"length": 0, "numeric": 1, "common": 2, "similarity": 3}


def build_password_rules():
    """Summarise the configured validators so the UI never invents rules."""
    rules = []
    for validator in get_default_password_validators():
        if isinstance(validator, MinimumLengthValidator):
            rules.append(
                {
                    "key": "length",
                    "label": f"Ít nhất {validator.min_length} ký tự",
                    "min_length": validator.min_length,
                }
            )
        elif isinstance(validator, NumericPasswordValidator):
            rules.append({"key": "numeric", "label": "Không chỉ gồm chữ số"})
        elif isinstance(validator, CommonPasswordValidator):
            rules.append({"key": "common", "label": "Không phải mật khẩu phổ biến"})
        elif isinstance(validator, UserAttributeSimilarityValidator):
            rules.append(
                {"key": "similarity", "label": "Không quá giống thông tin cá nhân"}
            )
        else:
            label = validator.get_help_text()
            if label:
                rules.append({"key": f"validator-{len(rules)}", "label": label})
    return sorted(rules, key=lambda rule: RULE_ORDER.get(rule["key"], 99))


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


class ProfileForm(forms.ModelForm):
    """Only the two personal fields a user may change themselves."""

    class Meta:
        model = User
        fields = ("ho_ten", "email")
        widgets = {
            "ho_ten": forms.TextInput(
                attrs={"class": "form-control", "autocomplete": "name"}
            ),
            "email": forms.EmailInput(
                attrs={"class": "form-control", "autocomplete": "email"}
            ),
        }
        error_messages = {
            "ho_ten": {"required": "Vui lòng nhập họ và tên."},
            "email": {"invalid": "Email không hợp lệ."},
        }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["ho_ten"].label = "Tên hiển thị"
        self.fields["email"].label = "Địa chỉ email"

    def clean_ho_ten(self):
        value = self.cleaned_data["ho_ten"].strip()
        if not value:
            raise forms.ValidationError("Vui lòng nhập họ và tên.")
        return value


class AccountPasswordChangeForm(PasswordChangeForm):
    error_messages = {
        **PasswordChangeForm.error_messages,
        "password_incorrect": "Mật khẩu hiện tại không đúng.",
        "password_mismatch": "Hai mật khẩu mới không khớp.",
    }

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        rules = build_password_rules()
        self.password_rules = rules
        self.password_min_length = next(
            (rule["min_length"] for rule in rules if rule["key"] == "length"),
            0,
        )
        self.password_has_numeric_rule = any(rule["key"] == "numeric" for rule in rules)
        labels = {
            "old_password": "Mật khẩu hiện tại",
            "new_password1": "Mật khẩu mới",
            "new_password2": "Xác nhận mật khẩu mới",
        }
        for name, label in labels.items():
            self.fields[name].label = label
            self.fields[name].widget.attrs["class"] = "form-control"


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
