"""Fixed core fields for each entry function.

Core fields describe data the existing screens already own. The designer can
place them, but it cannot change their type or key. Required core fields
cannot be hidden or removed.

Activity and project identity fields are read-only echoes on the phiếu. The
activity, month, and project system blocks stay the existing entry widgets.
Indicator core keys are locked cards: the current grid already renders those
columns, and a chỉ tiêu template only adds custom per-row columns.
"""

from dataclasses import dataclass


@dataclass(frozen=True)
class CoreField:
    core_key: str
    key: str
    label: str
    field_type: str
    required: bool
    read_only: bool = True
    system_block: bool = False
    grid_column: bool = False


def _field(core_key, label, field_type, *, required, **flags):
    return CoreField(
        core_key=core_key,
        key=core_key,
        label=label,
        field_type=field_type,
        required=required,
        **flags,
    )


ACTIVITY_FIELDS = (
    _field("ten", "Tên hoạt động", "text", required=True),
    _field("tu_ngay", "Từ ngày", "date", required=True),
    _field("den_ngay", "Đến ngày", "date", required=False),
    _field("dia_diem", "Địa điểm", "text", required=False),
    _field("hinh_thuc", "Hình thức", "select", required=False),
    _field("linh_vuc", "Lĩnh vực", "lookup", required=False),
    _field(
        "doi_tuong_huong_toi", "Đối tượng hướng tới", "multi_select", required=False
    ),
    _field("don_vi_phoi_hop", "Đơn vị phối hợp", "text", required=False),
    _field("noi_dung", "Nội dung", "textarea", required=False),
    _field("ket_qua", "Kết quả", "textarea", required=False),
    _field(
        "so_lieu_grid",
        "Số liệu chỉ tiêu",
        "instruction",
        required=True,
        system_block=True,
    ),
)

PROJECT_FIELDS = (
    _field("ten_du_an", "Tên dự án", "text", required=True),
    _field("chuong_trinh", "Chương trình", "select", required=True),
    _field("hinh_thuc", "Hình thức", "select", required=True),
    _field("nam", "Năm", "integer", required=True),
    _field("phong", "Phòng ban", "lookup", required=True),
    _field(
        "ho_tro",
        "Dòng hỗ trợ dự án",
        "instruction",
        required=True,
        system_block=True,
    ),
)

MONTH_FIELDS = (
    _field(
        "bang_chi_tieu",
        "Bảng chỉ tiêu tháng",
        "instruction",
        required=True,
        system_block=True,
    ),
)

INDICATOR_FIELDS = (
    _field("gia_tri", "Giá trị", "decimal", required=True, grid_column=True),
    _field("doi_tuong", "Đối tượng", "lookup", required=True, grid_column=True),
    _field("linh_vuc", "Lĩnh vực", "lookup", required=True, grid_column=True),
    _field("nguon", "Nguồn số liệu", "lookup", required=True, grid_column=True),
    _field("ghi_chu", "Ghi chú dòng", "textarea", required=True, grid_column=True),
)

REGISTRY = {
    "hoat_dong": ACTIVITY_FIELDS,
    "du_an": PROJECT_FIELDS,
    "thang": MONTH_FIELDS,
    "chi_tieu": INDICATOR_FIELDS,
}


def core_fields_for(function_type):
    return REGISTRY.get(function_type, ())


def get_core_field(function_type, core_key):
    for field in core_fields_for(function_type):
        if field.core_key == core_key:
            return field
    return None


def required_core_keys(function_type):
    return frozenset(
        field.core_key for field in core_fields_for(function_type) if field.required
    )
