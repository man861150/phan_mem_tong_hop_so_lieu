"""Activity types, activities, partner units, and projects."""

from django import forms
from django.contrib import admin, messages
from simple_history.admin import SimpleHistoryAdmin

from apps.activities.models import (
    DonViPhoiHop,
    DuAn,
    HoatDong,
    HoatDongDonVi,
)
from apps.catalog.admin import CatalogPermissionMixin


class DonViPhoiHopForm(forms.ModelForm):
    # Keep a trailing space so "Đại học A" and "Đại học A " can both be stored.
    ten_don_vi = forms.CharField(label="Tên đơn vị", max_length=255, strip=False)

    class Meta:
        model = DonViPhoiHop
        fields = ("ten_don_vi", "doi_tuong")


def _is_history_model(model):
    return model._meta.model_name.startswith("historical")


def repoint_don_vi(keeper, duplicates):
    """Move every current foreign key and M2M row onto the keeper."""
    dup_ids = [row.pk for row in duplicates]
    moved = 0
    for rel in keeper._meta.related_objects:
        if _is_history_model(rel.related_model):
            continue
        if rel.many_to_many:
            through = rel.through
            fk_names = [
                field.attname
                for field in through._meta.fields
                if getattr(field, "remote_field", None) is not None
                and field.remote_field.model is type(keeper)
            ]
            for fk_name in fk_names:
                rows = list(
                    through._default_manager.filter(**{f"{fk_name}__in": dup_ids})
                )
                for row in rows:
                    setattr(row, fk_name, keeper.pk)
                    row.save()
                    moved += 1
            continue
        field_name = rel.field.attname
        rows = list(
            rel.related_model._default_manager.filter(**{f"{field_name}__in": dup_ids})
        )
        for row in rows:
            setattr(row, field_name, keeper.pk)
            row.save()
            moved += 1
    return moved


@admin.action(description="Gộp đơn vị trùng")
def gop_don_vi_trung(modeladmin, request, queryset):
    rows = list(queryset.order_by("id"))
    if len(rows) < 2:
        modeladmin.message_user(
            request,
            "Chọn ít nhất hai đơn vị để gộp.",
            level=messages.WARNING,
        )
        return
    exact = [row for row in rows if row.ten_don_vi == row.ten_don_vi.strip()]
    pool = exact or rows
    keeper = min(pool, key=lambda row: row.pk)
    duplicates = [row for row in rows if row.pk != keeper.pk]
    keeper.ten_don_vi = keeper.ten_don_vi.strip()
    keeper._change_reason = "Gộp đơn vị trùng"
    keeper.save()
    moved = repoint_don_vi(keeper, duplicates)
    for row in duplicates:
        row._change_reason = "Gộp đơn vị trùng"
        row.delete()
    modeladmin.message_user(
        request,
        f"Đã gộp {len(duplicates)} đơn vị vào “{keeper}”, chuyển {moved} dòng liên kết.",
    )


@admin.register(DonViPhoiHop)
class DonViPhoiHopAdmin(CatalogPermissionMixin, SimpleHistoryAdmin):
    form = DonViPhoiHopForm
    list_display = ("ten_don_vi", "doi_tuong")
    list_filter = ("doi_tuong",)
    search_fields = ("ten_don_vi",)
    ordering = ("ten_don_vi", "id")
    actions = (gop_don_vi_trung,)


class HoatDongDonViInline(admin.TabularInline):
    model = HoatDongDonVi
    extra = 0
    autocomplete_fields = ("don_vi",)


@admin.register(HoatDong)
class HoatDongAdmin(SimpleHistoryAdmin):
    list_display = (
        "ten",
        "loai_hoat_dong",
        "tu_ngay",
        "den_ngay",
        "trang_thai",
    )
    list_filter = (
        "trang_thai",
        "hinh_thuc",
        "loai_hoat_dong__phong",
        "loai_hoat_dong",
    )
    search_fields = ("ten", "dia_diem")
    date_hierarchy = "tu_ngay"
    filter_horizontal = ("doi_tuong_huong_toi",)
    inlines = (HoatDongDonViInline,)
    ordering = ("-tu_ngay", "-id")


@admin.register(DuAn)
class DuAnAdmin(SimpleHistoryAdmin):
    list_display = ("ten_du_an", "phong", "chuong_trinh", "hinh_thuc", "nam")
    list_filter = ("phong", "chuong_trinh", "hinh_thuc", "nam")
    search_fields = ("ten_du_an",)
    ordering = ("-nam", "ten_du_an", "id")
