"""Users, roles, and department scope."""

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib import admin, messages
from django.contrib.auth.admin import UserAdmin as DjangoUserAdmin
from simple_history.admin import SimpleHistoryAdmin

from apps.accounts.forms import UserAdminChangeForm, UserAdminCreationForm
from apps.accounts.models import User
from apps.accounts.permissions import can
from apps.accounts.roles import Role
from config.admin_display import ROLE_TONE, pill

ROLE_HELP = (
    "Cán bộ nhập liệu và lãnh đạo phòng phải thuộc một phòng ban. "
    "Quản trị hệ thống được vào cổng này. "
    "Lãnh đạo Trung tâm chỉ xem báo cáo trên ứng dụng chính."
)
PHONG_HELP = (
    "Bắt buộc với cán bộ nhập liệu và lãnh đạo phòng. "
    "Để trống với quản trị hệ thống và lãnh đạo Trung tâm."
)
ACTIVE_HELP = (
    "Bỏ chọn để ngừng tài khoản. Người dùng không đăng nhập được cho đến khi bật lại."
)
ROLE_FIELDSET_HELP = (
    "Cán bộ nhập liệu và lãnh đạo phòng phải gắn một phòng ban. "
    "Lãnh đạo Trung tâm không dùng trang quản trị. "
    "Quản trị hệ thống được cấp quyền vào cổng này khi lưu."
)


@admin.action(description="Mở khóa tài khoản")
def mo_khoa_tai_khoan(modeladmin, request, queryset):
    from axes.utils import reset

    removed = 0
    for user in queryset:
        removed += reset(username=user.username)
    modeladmin.message_user(
        request,
        f"Đã mở khóa {queryset.count()} tài khoản, xóa {removed} lượt đăng nhập sai.",
        level=messages.SUCCESS,
    )


@admin.register(User)
class UserAdmin(SimpleHistoryAdmin, DjangoUserAdmin):
    form = UserAdminChangeForm
    add_form = UserAdminCreationForm
    list_display = (
        "username",
        "ho_ten",
        "email",
        "vai_tro",
        "phong",
        "trang_thai_hoat_dong",
    )
    list_filter = ("role", "is_active", "phong")
    list_select_related = ("phong",)
    search_fields = ("username", "ho_ten", "email")
    search_help_text = "Tìm theo tên đăng nhập, họ tên hoặc email."
    ordering = ("username",)
    filter_horizontal = ()
    actions = (mo_khoa_tai_khoan,)
    fieldsets = (
        (
            "Tài khoản",
            {
                "fields": ("username", "password"),
                "description": (
                    "Tên đăng nhập dùng để vào hệ thống. "
                    "Mật khẩu đổi tại biểu mẫu này hoặc người dùng tự đổi trong Hồ sơ."
                ),
            },
        ),
        (
            "Vai trò và phòng ban",
            {
                "fields": ("ho_ten", "email", "role", "phong"),
                "description": ROLE_FIELDSET_HELP,
            },
        ),
        (
            "Trạng thái",
            {
                "fields": ("is_active",),
                "description": (
                    "Ngừng hoạt động thì tài khoản không đăng nhập được. "
                    "Đăng nhập sai quá nhiều lần thì chọn tài khoản và chạy "
                    "Mở khóa tài khoản."
                ),
            },
        ),
    )
    add_fieldsets = (
        (
            "Tài khoản",
            {
                "classes": ("wide",),
                "fields": ("username", "usable_password", "password1", "password2"),
            },
        ),
        (
            "Vai trò và phòng ban",
            {
                "fields": ("ho_ten", "email", "role", "phong"),
                "description": ROLE_FIELDSET_HELP,
            },
        ),
        ("Trạng thái", {"fields": ("is_active",)}),
    )

    @admin.display(description="Vai trò", ordering="role")
    def vai_tro(self, obj):
        return pill(obj.get_role_display(), ROLE_TONE.get(obj.role, "inactive"))

    @admin.display(description="Trạng thái", ordering="is_active")
    def trang_thai_hoat_dong(self, obj):
        if obj.is_active:
            return pill("Đang hoạt động", "active")
        return pill("Ngừng hoạt động", "inactive")

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        help_text = {
            "role": ROLE_HELP,
            "phong": PHONG_HELP,
            "is_active": ACTIVE_HELP,
        }
        for name, text in help_text.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

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


@admin.register(AccessAttempt)
class AccessAttemptAdmin(admin.ModelAdmin):
    """Failed logins that can still lock a username and IP pair.

    POST bodies are omitted so a mistyped password is not shown here.
    """

    list_display = (
        "ten_dang_nhap",
        "dia_chi_ip",
        "so_lan_sai",
        "thoi_diem",
        "duong_dan",
    )
    search_fields = ("username", "ip_address")
    search_help_text = "Tìm theo tên đăng nhập hoặc địa chỉ IP."
    ordering = ("-attempt_time",)
    list_per_page = 50
    actions = ("mo_khoa_luot",)
    readonly_fields = (
        "ten_dang_nhap",
        "dia_chi_ip",
        "so_lan_sai",
        "thoi_diem",
        "duong_dan",
        "trinh_duyet",
    )
    fields = readonly_fields

    @admin.display(description="Tên đăng nhập", ordering="username")
    def ten_dang_nhap(self, obj):
        return obj.username

    @admin.display(description="Địa chỉ IP", ordering="ip_address")
    def dia_chi_ip(self, obj):
        return obj.ip_address

    @admin.display(description="Đường dẫn", ordering="path_info")
    def duong_dan(self, obj):
        return obj.path_info

    @admin.display(description="Trình duyệt", ordering="user_agent")
    def trinh_duyet(self, obj):
        return obj.user_agent

    @admin.display(description="Thời điểm", ordering="attempt_time")
    def thoi_diem(self, obj):
        return obj.attempt_time

    @admin.display(description="Số lần sai", ordering="failures_since_start")
    def so_lan_sai(self, obj):
        limit = settings.AXES_FAILURE_LIMIT
        if obj.failures_since_start >= limit:
            return pill(f"Đã khóa ({obj.failures_since_start})", "locked")
        return pill(f"{obj.failures_since_start} lần", "draft")

    @admin.action(description="Mở khóa các lượt đã chọn", permissions=["delete"])
    def mo_khoa_luot(self, request, queryset):
        count = queryset.count()
        queryset.delete()
        self.message_user(
            request,
            f"Đã xóa {count} lượt đăng nhập sai. Những tài khoản này có thể đăng nhập lại.",
        )

    def has_module_permission(self, request):
        return can(request.user, "manage_users")

    def has_view_permission(self, request, obj=None):
        return can(request.user, "manage_users")

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return can(request.user, "manage_users")

    def get_actions(self, request):
        actions = super().get_actions(request)
        actions.pop("delete_selected", None)
        return actions
