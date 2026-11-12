"""Role codes and the two roles that are limited to one department."""

from django.db import models


class Role(models.TextChoices):
    ENTRY_OFFICER = "entry_officer", "Cán bộ nhập liệu"
    DEPARTMENT_HEAD = "department_head", "Lãnh đạo phòng"
    CENTER_HEAD = "center_head", "Lãnh đạo Trung tâm"
    SYSTEM_ADMIN = "system_admin", "Quản trị hệ thống"


SCOPED_ROLES = frozenset({Role.ENTRY_OFFICER, Role.DEPARTMENT_HEAD})

SCOPED_ROLE_DEPARTMENT_ERROR = (
    "Cán bộ nhập liệu và lãnh đạo phòng phải thuộc một phòng ban."
)
