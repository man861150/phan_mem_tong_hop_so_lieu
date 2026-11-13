"""Departments, indicators, annual plans, lookup tables, and form templates."""

from django.conf import settings
from django.contrib import admin, messages
from django.core.exceptions import PermissionDenied
from django.core.management.base import CommandError
from django.db import transaction
from django.http import HttpResponseRedirect
from django.urls import path, reverse
from simple_history.admin import SimpleHistoryAdmin

from apps.accounts.permissions import can
from apps.accounts.scoping import scoped
from apps.catalog.management.commands.load_linh_vuc import (
    CONFIRMATION,
    INSTRUCTION,
    load_linh_vuc,
)
from apps.catalog.models import (
    BieuMauChiTieu,
    ChiTieu,
    ChiTieuKeHoach,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    KyBaoCao,
    LoaiHoatDong,
    NguonSoLieu,
    NhomChiTieu,
    PhongBan,
    TrangThaiKy,
)


class CatalogPermissionMixin:
    """Staff screens follow can(). system_admin holds manage_catalog."""

    permission_action = "manage_catalog"

    def has_module_permission(self, request):
        return can(request.user, self.permission_action)

    def has_view_permission(self, request, obj=None):
        return can(request.user, self.permission_action)

    def has_add_permission(self, request):
        return can(request.user, self.permission_action)

    def has_change_permission(self, request, obj=None):
        return can(request.user, self.permission_action)

    def has_delete_permission(self, request, obj=None):
        return can(request.user, self.permission_action)


class DepartmentScopedAdminMixin:
    """Limit the changelist with scoped(). Unscoped roles see every phòng."""

    scope_field = "phong_id"

    def get_queryset(self, request):
        return scoped(request.user, super().get_queryset(request), self.scope_field)


class NhomChiTieuInline(admin.TabularInline):
    model = NhomChiTieu
    extra = 0
    ordering = ("thu_tu", "id")
    fields = ("ten_mang", "thu_tu")


@admin.register(PhongBan)
class PhongBanAdmin(CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin):
    scope_field = "id"
    list_display = ("ma_phong", "ten_phong", "dang_su_dung")
    list_filter = ("dang_su_dung",)
    search_fields = ("ma_phong", "ten_phong")
    ordering = ("ma_phong",)
    inlines = (NhomChiTieuInline,)


@admin.register(NhomChiTieu)
class NhomChiTieuAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    list_display = ("ten_mang", "phong", "thu_tu")
    list_filter = ("phong",)
    search_fields = ("ten_mang",)
    ordering = ("thu_tu", "ten_mang")
    list_select_related = ("phong",)


@admin.register(ChiTieu)
class ChiTieuAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    scope_field = "nhom__phong_id"
    list_display = (
        "ma_chi_tieu",
        "ten_chi_tieu",
        "nhom",
        "kieu_ghi_nhan",
        "cach_tong_hop",
        "dang_su_dung",
    )
    list_filter = ("nhom__phong", "kieu_ghi_nhan", "cach_tong_hop", "dang_su_dung")
    search_fields = ("ma_chi_tieu", "ten_chi_tieu")
    ordering = ("ma_chi_tieu",)
    list_select_related = ("nhom", "nhom__phong")
    fieldsets = (
        (
            None,
            {
                "fields": (
                    "ma_chi_tieu",
                    "ten_chi_tieu",
                    "don_vi_tinh",
                    "nhom",
                    "chi_tieu_cha",
                    "dang_su_dung",
                )
            },
        ),
        (
            "Cách ghi nhận",
            {
                "fields": (
                    "kieu_ghi_nhan",
                    "cach_tong_hop",
                    "count_subject",
                    "loai_hoat_dong",
                    "loai_ho_tro",
                    "chi_tieu_tu_so",
                    "chi_tieu_mau_so",
                    "khong_vuot_chi_tieu",
                    "phan_loai_doi_tuong",
                    "phan_loai_linh_vuc",
                    "doi_tuong_ap_dung",
                    "nguon_cho_phep",
                )
            },
        ),
        (
            "Giới hạn giá trị",
            {
                "fields": ("gia_tri_toi_thieu", "gia_tri_toi_da"),
                "description": (
                    "Để trống nếu chỉ tiêu chỉ cần không âm. Khi cả hai "
                    "được nhập, giá trị tối thiểu không được lớn hơn tối đa."
                ),
            },
        ),
    )
    filter_horizontal = ("doi_tuong_ap_dung", "nguon_cho_phep")


@admin.register(DanhMucDoiTuong)
class DanhMucDoiTuongAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    list_display = ("ten_doi_tuong",)
    search_fields = ("ten_doi_tuong",)
    ordering = ("ten_doi_tuong",)


@admin.register(DanhMucLinhVuc)
class DanhMucLinhVucAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    list_display = ("he_thong", "ma", "ten", "cap", "cha")
    list_filter = ("he_thong",)
    search_fields = ("ma", "ten")
    ordering = ("he_thong", "ma")
    list_select_related = ("cha",)
    change_list_template = "admin/catalog/danhmuc_linh_vuc/change_list.html"

    def get_urls(self):
        urls = super().get_urls()
        custom = [
            path(
                "nap-fixtures/",
                self.admin_site.admin_view(self.load_fixtures),
                name="catalog_danhmuc_linh_vuc_load",
            ),
        ]
        return custom + urls

    def load_fixtures(self, request):
        if not self.has_change_permission(request):
            raise PermissionDenied
        csv_path = settings.BASE_DIR / "fixtures" / "linh_vuc.csv"
        if not csv_path.is_file():
            messages.warning(request, INSTRUCTION)
        else:
            try:
                counts = load_linh_vuc(csv_path)
            except CommandError as exc:
                messages.error(request, str(exc))
            else:
                messages.success(
                    request,
                    "Đã nạp fixtures/linh_vuc.csv: "
                    f"tạo mới {counts['created']}, "
                    f"cập nhật {counts['updated']}, "
                    f"giữ nguyên {counts['unchanged']}. "
                    + CONFIRMATION,
                )
        return HttpResponseRedirect(
            reverse("admin:catalog_danhmuclinhvuc_changelist")
        )


@admin.register(NguonSoLieu)
class NguonSoLieuAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    list_display = ("ten_nguon",)
    search_fields = ("ten_nguon",)
    ordering = ("ten_nguon",)


class BieuMauChiTieuInline(admin.TabularInline):
    model = BieuMauChiTieu
    extra = 0
    ordering = ("thu_tu", "id")
    fields = ("chi_tieu", "bat_buoc", "thu_tu")

    def get_queryset(self, request):
        return super().get_queryset(request).order_by("thu_tu", "id")

    def formfield_for_foreignkey(self, db_field, request, **kwargs):
        if db_field.name == "chi_tieu":
            object_id = request.resolver_match.kwargs.get("object_id")
            if object_id:
                phong_id = LoaiHoatDong.objects.values_list("phong_id", flat=True).get(
                    pk=object_id
                )
                kwargs["queryset"] = ChiTieu.objects.filter(
                    nhom__phong_id=phong_id
                ).order_by("ma_chi_tieu")
        return super().formfield_for_foreignkey(db_field, request, **kwargs)


@admin.register(LoaiHoatDong)
class LoaiHoatDongAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    list_display = ("ten_loai", "phong", "co_ke_hoach_so_luong")
    list_filter = ("phong", "co_ke_hoach_so_luong")
    search_fields = ("ten_loai",)
    ordering = ("ten_loai",)
    list_select_related = ("phong",)
    inlines = (BieuMauChiTieuInline,)


@admin.register(BieuMauChiTieu)
class BieuMauChiTieuAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    scope_field = "loai_hoat_dong__phong_id"
    list_display = ("loai_hoat_dong", "chi_tieu", "bat_buoc", "thu_tu")
    list_filter = ("loai_hoat_dong__phong", "bat_buoc")
    ordering = ("thu_tu", "id")
    list_select_related = ("loai_hoat_dong", "chi_tieu")


@admin.register(ChiTieuKeHoach)
class ChiTieuKeHoachAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    scope_field = "chi_tieu__nhom__phong_id"
    list_display = ("chi_tieu", "nam", "gia_tri_ke_hoach", "doi_tuong", "trang_thai")
    list_filter = ("nam", "trang_thai", "chi_tieu__nhom__phong")
    search_fields = ("chi_tieu__ma_chi_tieu", "chi_tieu__ten_chi_tieu", "ly_do")
    ordering = ("-nam", "chi_tieu")
    list_select_related = ("chi_tieu", "doi_tuong")

    def save_model(self, request, obj, form, change):
        if (obj.ly_do or "").strip():
            obj._change_reason = obj.ly_do.strip()
        super().save_model(request, obj, form, change)


@admin.register(KyBaoCao)
class KyBaoCaoAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    permission_action = "manage_periods"
    list_display = ("nam", "so_ky", "tu_ngay", "den_ngay", "trang_thai", "loai_ky")
    list_filter = ("nam", "trang_thai")
    ordering = ("-nam", "-so_ky")
    actions = ("mo_ky", "khoa_ky")

    @admin.action(description="Mở kỳ")
    def mo_ky(self, request, queryset):
        self._dat_trang_thai(request, queryset, TrangThaiKy.MO, "Mở kỳ báo cáo", "mở")

    @admin.action(description="Khóa kỳ")
    def khoa_ky(self, request, queryset):
        self._dat_trang_thai(
            request, queryset, TrangThaiKy.KHOA, "Khóa kỳ báo cáo", "khóa"
        )

    def _dat_trang_thai(self, request, queryset, trang_thai, reason, verb):
        count = 0
        for row in queryset:
            # Same lock order as entry saves: the period first.
            with transaction.atomic():
                locked = KyBaoCao.objects.select_for_update().get(pk=row.pk)
                locked.trang_thai = trang_thai
                locked._change_reason = reason
                locked.save()
            count += 1
        self.message_user(request, f"Đã {verb} {count} kỳ.")
