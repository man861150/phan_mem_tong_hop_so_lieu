"""Aggregation, Excel export, Word export, and published reports."""

from django.contrib import admin

from apps.reporting.models import BaoCaoDaXuat, BaoCaoDaXuatDong
from config.admin_portal import READONLY_GUIDANCE, GuidanceMixin


class BaoCaoDaXuatDongInline(admin.TabularInline):
    model = BaoCaoDaXuatDong
    extra = 0
    can_delete = False
    fields = (
        "ten_chi_tieu",
        "phong",
        "period_value",
        "cumulative",
        "plan",
        "percent",
        "note",
        "danh_gia",
        "breakdown_label",
    )
    readonly_fields = fields
    ordering = ("id",)

    def has_add_permission(self, request, obj=None):
        return False


@admin.register(BaoCaoDaXuat)
class BaoCaoDaXuatAdmin(GuidanceMixin, admin.ModelAdmin):
    """Reports are inserted by the export views; admin is read-only."""

    guidance = READONLY_GUIDANCE
    list_per_page = 50
    list_display = (
        "id",
        "ky",
        "phong",
        "nguoi_lap",
        "ngay_lap",
        "dinh_dang",
        "file",
    )
    list_filter = ("dinh_dang", "phong")
    search_fields = ("ky", "nguoi_lap__username", "file")
    search_help_text = "Tìm theo kỳ, tên đăng nhập người lập hoặc tên tệp."
    date_hierarchy = "ngay_lap"
    ordering = ("-ngay_lap", "-id")
    list_select_related = ("phong", "nguoi_lap")
    readonly_fields = (
        "ky",
        "phong",
        "nguoi_lap",
        "ngay_lap",
        "dinh_dang",
        "file",
    )
    inlines = (BaoCaoDaXuatDongInline,)

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_view_permission(self, request, obj=None):
        return request.user.is_staff

    def has_delete_permission(self, request, obj=None):
        return False

    def get_readonly_fields(self, request, obj=None):
        return self.readonly_fields

    def get_queryset(self, request):
        return (
            super()
            .get_queryset(request)
            .select_related(
                "phong",
                "nguoi_lap",
            )
        )

    def has_module_permission(self, request):
        return request.user.is_staff
