"""Users, roles, and department scope."""

from django.contrib.auth.models import AbstractUser
from django.contrib.auth.validators import UnicodeUsernameValidator
from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.accounts.roles import SCOPED_ROLE_DEPARTMENT_ERROR, SCOPED_ROLES, Role

username_validator = UnicodeUsernameValidator()


class User(AbstractUser):
    username = models.CharField(
        "Tên đăng nhập",
        max_length=150,
        unique=True,
        help_text=(
            "Bắt buộc. Tối đa 150 ký tự. Chỉ gồm chữ cái, chữ số và @/./+/-/_."
        ),
        validators=[username_validator],
        error_messages={"unique": "Tên đăng nhập đã được sử dụng."},
    )
    ho_ten = models.CharField("Họ và tên", max_length=255)
    email = models.EmailField("Email", blank=True)
    role = models.CharField("Vai trò", max_length=32, choices=Role.choices)
    phong = models.ForeignKey(
        "catalog.PhongBan",
        verbose_name="Phòng ban",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="users",
    )
    history = HistoricalRecords()

    REQUIRED_FIELDS = ["email", "ho_ten", "role"]

    class Meta:
        verbose_name = "Người dùng"
        verbose_name_plural = "Người dùng"

    def __str__(self):
        return self.ho_ten or self.username

    @property
    def initials(self) -> str:
        """Up to two initials for the header avatar, with a safe fallback."""
        name = (self.ho_ten or "").strip() or (self.username or "").strip()
        words = name.split()
        if not words:
            return "?"
        if len(words) == 1:
            return words[0][:2].upper()
        return f"{words[0][0]}{words[-1][0]}".upper()

    def clean(self):
        super().clean()
        if self.role in SCOPED_ROLES and self.phong_id is None:
            raise ValidationError({"phong": SCOPED_ROLE_DEPARTMENT_ERROR})

    def save(self, *args, **kwargs):
        # last_login updates must not revalidate the whole account.
        if not kwargs.get("update_fields"):
            self.full_clean()
        return super().save(*args, **kwargs)
