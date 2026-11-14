"""Allow-listed catalog lookups for custom fields.

The posted value is a primary key. Labels are resolved on display and are
never trusted from the request. Partner units have no department column, so
any existing row is in scope. Shared catalogs have no active flag.
"""

from django.core.exceptions import ValidationError

from apps.activities.models import DonViPhoiHop
from apps.catalog.models import (
    ChiTieu,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    NguonSoLieu,
    PhongBan,
)

CATALOG_KEYS = frozenset(
    {
        "doi_tuong",
        "linh_vuc",
        "nguon_so_lieu",
        "don_vi_phoi_hop",
        "phong_ban",
        "chi_tieu",
    }
)

CATALOG_LABELS = {
    "doi_tuong": "Đối tượng",
    "linh_vuc": "Lĩnh vực",
    "nguon_so_lieu": "Nguồn số liệu",
    "don_vi_phoi_hop": "Đơn vị phối hợp",
    "phong_ban": "Phòng ban",
    "chi_tieu": "Chỉ tiêu",
}


def lookup_queryset(catalog_key, phong_id):
    if catalog_key == "doi_tuong":
        return DanhMucDoiTuong.objects.all()
    if catalog_key == "linh_vuc":
        return DanhMucLinhVuc.objects.all()
    if catalog_key == "nguon_so_lieu":
        return NguonSoLieu.objects.all()
    if catalog_key == "don_vi_phoi_hop":
        return DonViPhoiHop.objects.all()
    if catalog_key == "phong_ban":
        return PhongBan.objects.filter(dang_su_dung=True)
    if catalog_key == "chi_tieu":
        return ChiTieu.objects.filter(
            dang_su_dung=True,
            nhom__phong_id=phong_id,
        )
    return None


def lookup_choices(catalog_key, phong_id):
    queryset = lookup_queryset(catalog_key, phong_id)
    if queryset is None:
        return []
    return [(str(obj.pk), str(obj)) for obj in queryset.order_by("pk")]


def resolve_lookup(catalog_key, raw_pk, phong_id):
    """Return the object or raise ValidationError. Empty input returns None."""
    if raw_pk is None or str(raw_pk).strip() == "":
        return None
    queryset = lookup_queryset(catalog_key, phong_id)
    if queryset is None:
        raise ValidationError("Danh mục không hợp lệ.")
    try:
        pk = int(raw_pk)
    except (TypeError, ValueError) as exc:
        raise ValidationError("Giá trị danh mục không hợp lệ.") from exc
    obj = queryset.filter(pk=pk).first()
    if obj is None:
        raise ValidationError("Giá trị không còn trong phạm vi phòng.")
    return obj
