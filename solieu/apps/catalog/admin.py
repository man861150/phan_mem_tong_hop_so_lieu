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
    TrangThaiKeHoach,
    TrangThaiKy,
)
from config.admin_display import pill
from config.admin_portal import LINH_VUC_GUIDANCE, PERIOD_GUIDANCE, GuidanceMixin

CHITIEU_HELP = {
    "kieu_ghi_nhan": (
        "Chọn phiếu nào được dùng để nhập chỉ tiêu này: hoạt động, tháng hoặc dự án."
    ),
    "cach_tong_hop": (
        "Cách cộng các phiếu thành số báo cáo. Tỷ lệ dùng tử số và mẫu số. "
        "Đếm dùng đối tượng đếm."
    ),
    "count_subject": "Chỉ điền khi cách tổng hợp là Đếm.",
    "chi_tieu_tu_so": (
        "Chỉ điền khi cách tổng hợp là Tỷ lệ. Cùng phòng với chỉ tiêu này."
    ),
    "chi_tieu_mau_so": (
        "Chỉ điền khi cách tổng hợp là Tỷ lệ. Cùng phòng với chỉ tiêu này."
    ),
    "khong_vuot_chi_tieu": "Nếu chọn, giá trị nhập không được vượt chỉ tiêu này.",
    "phan_loai_doi_tuong": "Bật khi số liệu tách theo đối tượng.",
    "phan_loai_linh_vuc": "Bật khi số liệu tách theo lĩnh vực.",
}


def _dang_su_dung(obj):
    if obj.dang_su_dung:
        return pill("Đang sử dụng", "active")
    return pill("Ngừng sử dụng", "inactive")


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
class PhongBanAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    scope_field = "id"
    list_display = ("ma_phong", "ten_phong", "trang_thai_su_dung")
    list_filter = ("dang_su_dung",)
    search_fields = ("ma_phong", "ten_phong")
    search_help_text = "Tìm theo mã phòng hoặc tên phòng."
    ordering = ("ma_phong",)
    inlines = (NhomChiTieuInline,)

    @admin.display(description="Trạng thái", ordering="dang_su_dung")
    def trang_thai_su_dung(self, obj):
        return _dang_su_dung(obj)


@admin.register(NhomChiTieu)
class NhomChiTieuAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    list_display = ("ten_mang", "phong", "thu_tu")
    list_filter = ("phong",)
    search_fields = ("ten_mang",)
    search_help_text = "Tìm theo tên mảng."
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
        "trang_thai_su_dung",
    )
    list_filter = ("nhom__phong", "kieu_ghi_nhan", "cach_tong_hop", "dang_su_dung")
    search_fields = ("ma_chi_tieu", "ten_chi_tieu")
    search_help_text = "Tìm theo mã chỉ tiêu hoặc tên chỉ tiêu."
    ordering = ("ma_chi_tieu",)
    list_select_related = ("nhom", "nhom__phong")

    @admin.display(description="Trạng thái", ordering="dang_su_dung")
    def trang_thai_su_dung(self, obj):
        return _dang_su_dung(obj)

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        for name, text in CHITIEU_HELP.items():
            if name in form.base_fields:
                form.base_fields[name].help_text = text
        return form

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
                "description": (
                    "Kiểu ghi nhận chọn cách nhập: theo hoạt động, theo tháng "
                    "hoặc theo dự án. Cách tổng hợp chọn cách cộng dồn: tổng, "
                    "đếm, lũy kế, tỷ lệ, trung bình hoặc mới nhất. Chỉ tiêu tỷ lệ "
                    "cần tử số và mẫu số. Chỉ tiêu đếm cần đối tượng đếm."
                ),
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
                ),
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
    search_help_text = "Tìm theo tên đối tượng."
    ordering = ("ten_doi_tuong",)


@admin.register(DanhMucLinhVuc)
class DanhMucLinhVucAdmin(GuidanceMixin, CatalogPermissionMixin, SimpleHistoryAdmin):
    guidance = LINH_VUC_GUIDANCE
    list_display = ("he_thong", "ma", "ten", "cap", "cha")
    list_filter = ("he_thong",)
    search_fields = ("ma", "ten")
    search_help_text = "Tìm theo mã hoặc tên lĩnh vực."
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
                    f"giữ nguyên {counts['unchanged']}. " + CONFIRMATION,
                )
        return HttpResponseRedirect(reverse("admin:catalog_danhmuclinhvuc_changelist"))


@admin.register(NguonSoLieu)
class NguonSoLieuAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    list_display = ("ten_nguon",)
    search_fields = ("ten_nguon",)
    search_help_text = "Tìm theo tên nguồn."
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
    search_help_text = "Tìm theo tên loại hoạt động."
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
    search_fields = (
        "loai_hoat_dong__ten_loai",
        "chi_tieu__ma_chi_tieu",
        "chi_tieu__ten_chi_tieu",
    )
    search_help_text = "Tìm theo tên loại hoạt động, mã chỉ tiêu hoặc tên chỉ tiêu."
    ordering = ("thu_tu", "id")
    list_select_related = ("loai_hoat_dong", "chi_tieu")


@admin.register(ChiTieuKeHoach)
class ChiTieuKeHoachAdmin(
    CatalogPermissionMixin, DepartmentScopedAdminMixin, SimpleHistoryAdmin
):
    scope_field = "chi_tieu__nhom__phong_id"
    list_display = (
        "chi_tieu",
        "nam",
        "gia_tri_ke_hoach",
        "doi_tuong",
        "trang_thai_ke_hoach",
    )
    list_filter = ("nam", "trang_thai", "chi_tieu__nhom__phong")
    search_fields = ("chi_tieu__ma_chi_tieu", "chi_tieu__ten_chi_tieu", "ly_do")
    search_help_text = "Tìm theo mã chỉ tiêu, tên chỉ tiêu hoặc lý do."
    ordering = ("-nam", "chi_tieu")
    list_select_related = ("chi_tieu", "doi_tuong")

    @admin.display(description="Trạng thái", ordering="trang_thai")
    def trang_thai_ke_hoach(self, obj):
        if obj.trang_thai == TrangThaiKeHoach.DA_XAC_NHAN:
            return pill("Đã xác nhận", "confirmed")
        return pill("Dự thảo", "draft")

    def save_model(self, request, obj, form, change):
        if (obj.ly_do or "").strip():
            obj._change_reason = obj.ly_do.strip()
        super().save_model(request, obj, form, change)


@admin.register(KyBaoCao)
class KyBaoCaoAdmin(GuidanceMixin, CatalogPermissionMixin, SimpleHistoryAdmin):
    guidance = PERIOD_GUIDANCE
    permission_action = "manage_periods"
    list_display = ("nam", "so_ky", "tu_ngay", "den_ngay", "trang_thai_ky", "loai_ky")
    list_filter = ("nam", "trang_thai")
    search_fields = ("nam",)
    search_help_text = "Nhập năm, ví dụ 2026."
    ordering = ("-nam", "-so_ky")
    actions = ("mo_ky", "khoa_ky")

    @admin.display(description="Trạng thái", ordering="trang_thai")
    def trang_thai_ky(self, obj):
        if obj.trang_thai == TrangThaiKy.MO:
            return pill("Đang mở", "open")
        return pill("Đã khóa", "locked")

    def get_search_results(self, request, queryset, search_term):
        term = (search_term or "").strip()
        if not term:
            return queryset, False
        if term.isdigit():
            return queryset.filter(nam=int(term)), False
        return queryset.none(), False

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
