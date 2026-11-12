"""Users, roles, and department scope."""

from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.accounts.forms import UserAdminChangeForm, UserAdminCreationForm
from apps.accounts.models import User
from apps.accounts.permissions import can
from apps.accounts.roles import Role


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    list_display = ("username", "ho_ten", "email", "role", "phong", "is_active")
    list_filter = ("role", "is_active", "phong")
    search_fields = ("username", "ho_ten", "email")
    ordering = ("username",)
    filter_horizontal = ()
    fieldsets = (
        (None, {"fields": ("username", "password")}),
        ("Thông tin", {"fields": ("ho_ten", "email", "role", "phong")}),
        ("Trạng thái", {"fields": ("is_active",)}),
    )
    add_fieldsets = (
        (
            None,
            {
                "classes": ("wide",),
                "fields": (
                    "username",
                    "ho_ten",
                    "email",
                    "role",
                    "phong",
                    "is_active",
                    "usable_password",
                    "password1",
                    "password2",
                ),
            },
        ),
    )

    def has_module_permission(self, request):
        return can(request.user, "manage_users")

    def has_view_permission(self, request, obj=None):
        return can(request.user, "manage_users")

    def has_add_permission(self, request):
        return can(request.user, "manage_users")

    def has_change_permission(self, request, obj=None):
        return can(request.user, "manage_users")

    def has_delete_permission(self, request, obj=None):
        return can(request.user, "manage_users")

    def save_model(self, request, obj, form, change):
        if obj.role == Role.SYSTEM_ADMIN:
            obj.is_staff = True
        else:
            obj.is_staff = False
            obj.is_superuser = False
        super().save_model(request, obj, form, change)
