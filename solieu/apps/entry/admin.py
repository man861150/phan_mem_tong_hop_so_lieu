"""Data-entry forms, indicator rows, project support, and approvals."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.entry.models import HoTroDuAn, LichSuXuLy, PhieuNhapLieu, SoLieu


@admin.register(PhieuNhapLieu)
class PhieuNhapLieuAdmin(SimpleHistoryAdmin):
    list_display = (
        "id",
        "phong",
        "loai_phieu",
        "doi_tuong",
        "trang_thai",
        "la_phieu_bo_sung",
        "nguoi_nhap",
        "ngay_gui",
    )
    list_filter = ("loai_phieu", "trang_thai", "phong", "la_phieu_bo_sung")
    search_fields = (
        "phong__ma_phong",
        "phong__ten_phong",
        "nguoi_nhap__username",
        "hoat_dong__ten",
        "du_an__ten_du_an",
    )
    autocomplete_fields = ("phong", "hoat_dong", "du_an", "nguoi_nhap")
    date_hierarchy = "ngay_gui"
    ordering = ("-id",)
    list_select_related = ("phong", "hoat_dong", "ky", "du_an", "nguoi_nhap")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "phong",
                    "loai_phieu",
                    "trang_thai",
                    "la_phieu_bo_sung",
                    "nguoi_nhap",
                    "ngay_gui",
                )
            },
        ),
        (
            "Đối tượng",
            {"fields": ("hoat_dong", "ky", "du_an")},
        ),
    )

    @admin.display(description="Đối tượng")
    def doi_tuong(self, obj):
        return obj.hoat_dong or obj.ky or obj.du_an


@admin.register(LichSuXuLy)
class LichSuXuLyAdmin(admin.ModelAdmin):
    list_display = (
        "phieu",
        "nguoi_xu_ly",
        "hanh_dong",
        "thoi_diem",
    )
    list_filter = ("hanh_dong", "phieu__phong")
    search_fields = (
        "phieu__hoat_dong__ten",
        "phieu__du_an__ten_du_an",
        "nguoi_xu_ly__username",
        "y_kien",
        "=phieu__id",
    )
    autocomplete_fields = ("phieu", "nguoi_xu_ly")
    date_hierarchy = "thoi_diem"
    ordering = ("-thoi_diem", "-id")
    list_select_related = ("phieu", "nguoi_xu_ly")
    readonly_fields = (
        "phieu",
        "nguoi_xu_ly",
        "hanh_dong",
        "y_kien",
        "thoi_diem",
    )

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


@admin.register(SoLieu)
class SoLieuAdmin(SimpleHistoryAdmin):
    list_display = (
        "phieu",
        "chi_tieu",
        "gia_tri",
        "doi_tuong",
        "linh_vuc",
        "nguon",
    )
    list_filter = ("chi_tieu__nhom__phong", "nguon", "doi_tuong", "linh_vuc")
    search_fields = (
        "chi_tieu__ma_chi_tieu",
        "chi_tieu__ten_chi_tieu",
        "ghi_chu",
        "=phieu__id",
    )
    autocomplete_fields = ("phieu", "chi_tieu", "doi_tuong", "linh_vuc", "nguon")
    ordering = ("phieu", "chi_tieu", "id")
    list_select_related = ("phieu", "chi_tieu", "doi_tuong", "linh_vuc", "nguon")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "phieu",
                    "chi_tieu",
                    "gia_tri",
                    "nguon",
                    "ghi_chu",
                )
            },
        ),
        (
            "Phân loại",
            {
                "fields": ("doi_tuong", "linh_vuc"),
                "description": "Chỉ chọn một trong hai: đối tượng hoặc lĩnh vực.",
            },
        ),
    )


@admin.register(HoTroDuAn)
class HoTroDuAnAdmin(SimpleHistoryAdmin):
    list_display = (
        "du_an",
        "phieu",
        "loai_ho_tro",
        "so_chuyen_gia",
        "ngay_ho_tro",
    )
    list_filter = ("loai_ho_tro", "du_an__phong", "ngay_ho_tro")
    search_fields = ("du_an__ten_du_an", "noi_dung", "=phieu__id")
    autocomplete_fields = ("du_an", "phieu")
    date_hierarchy = "ngay_ho_tro"
    ordering = ("-ngay_ho_tro", "-id")
    list_select_related = ("du_an", "phieu")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "du_an",
                    "phieu",
                    "loai_ho_tro",
                    "ngay_ho_tro",
                    "so_chuyen_gia",
                    "noi_dung",
                )
            },
        ),
    )
