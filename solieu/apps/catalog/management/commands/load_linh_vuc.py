"""Load the field-code tree from fixtures/linh_vuc.csv when that file exists."""

import csv

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.catalog.models import DanhMucLinhVuc, HeThongLinhVuc

INSTRUCTION = (
    "Chưa có file fixtures/linh_vuc.csv. Đặt file UTF-8 với các cột "
    "he_thong,ma,ten,cap,ma_cha (ma_cha để trống nếu là nút gốc) rồi chạy lại lệnh. "
    "Các mã lĩnh vực đã có được giữ nguyên."
)
CONFIRMATION = (
    "Kiểm tra lại với danh mục đã được ký trước khi nhập số liệu chính thức."
)
COLUMNS = ["he_thong", "ma", "ten", "cap", "ma_cha"]
ALLOWED = {HeThongLinhVuc.QD36, HeThongLinhVuc.TT24}


class Command(BaseCommand):
    help = (
        "Nạp cây lĩnh vực từ fixtures/linh_vuc.csv nếu file có sẵn. "
        "Không xóa mã đã có khi file vắng hoặc khi một dòng lỗi."
    )

    def handle(self, *args, **options):
        path = settings.BASE_DIR / "fixtures" / "linh_vuc.csv"
        if not path.is_file():
            self.stdout.write(INSTRUCTION)
            return
        counts = load_linh_vuc(path, self.stdout)
        self.stdout.write(
            "Đã nạp fixtures/linh_vuc.csv: "
            f"tạo mới {counts['created']}, "
            f"cập nhật {counts['updated']}, "
            f"giữ nguyên {counts['unchanged']}. "
            + CONFIRMATION
        )


@transaction.atomic
def load_linh_vuc(path, stdout=None):
    with path.open(encoding="utf-8-sig", newline="") as handle:
        reader = csv.DictReader(handle)
        if reader.fieldnames != COLUMNS:
            raise CommandError(
                "File fixtures/linh_vuc.csv phải có đúng các cột "
                "he_thong,ma,ten,cap,ma_cha."
            )
        rows = []
        for line_no, raw in enumerate(reader, start=2):
            if not any((raw.get(column) or "").strip() for column in COLUMNS):
                continue
            rows.append((line_no, {column: (raw.get(column) or "").strip() for column in COLUMNS}))

    counts = {"created": 0, "updated": 0, "unchanged": 0}
    saved = []
    for line_no, row in rows:
        line_no, row, obj, status = _upsert_row(line_no, row)
        counts[status] += 1
        saved.append((line_no, row, obj, status))
    for line_no, row, obj, status in saved:
        changed = _link_parent(line_no, row, obj, stdout)
        if changed and status == "unchanged":
            counts["unchanged"] -= 1
            counts["updated"] += 1
    return counts


def _upsert_row(line_no, row):
    he_thong = row["he_thong"]
    ma = row["ma"]
    ten = row["ten"]
    if he_thong not in ALLOWED:
        raise CommandError(
            f"Dòng {line_no}: hệ thống {he_thong!r} không hợp lệ. Chỉ dùng qd36 hoặc tt24."
        )
    if not ma or not ten:
        raise CommandError(f"Dòng {line_no}: mã và tên không được để trống.")
    try:
        cap = int(row["cap"])
    except ValueError as exc:
        raise CommandError(f"Dòng {line_no}: cấp {row['cap']!r} không phải số nguyên.") from exc
    if cap < 1:
        raise CommandError(f"Dòng {line_no}: cấp phải từ 1 trở lên.")
    obj = DanhMucLinhVuc.objects.filter(he_thong=he_thong, ma=ma).first()
    if obj is None:
        obj = DanhMucLinhVuc(he_thong=he_thong, ma=ma, ten=ten, cap=cap)
        obj.save()
        return line_no, row, obj, "created"
    changed = False
    if obj.ten != ten:
        obj.ten = ten
        changed = True
    if obj.cap != cap:
        obj.cap = cap
        changed = True
    if changed:
        obj.save()
        return line_no, row, obj, "updated"
    return line_no, row, obj, "unchanged"


def _link_parent(line_no, row, obj, stdout):
    parent_code = row["ma_cha"]
    if not parent_code:
        parent = None
    else:
        parent = DanhMucLinhVuc.objects.filter(
            he_thong=row["he_thong"], ma=parent_code
        ).first()
        if parent is None:
            text = ",".join(row[column] for column in COLUMNS)
            if stdout is not None:
                stdout.write(
                    f"Dòng {line_no}: không tìm thấy mã cha {parent_code} "
                    f"cùng hệ thống {row['he_thong']} cho mã {row['ma']}. {text}"
                )
            raise CommandError(
                f"Dòng {line_no}: không tìm thấy mã cha {parent_code}."
            )
    parent_id = None if parent is None else parent.pk
    if obj.cha_id != parent_id:
        obj.cha = parent
        obj.save()
        return True
    return False
