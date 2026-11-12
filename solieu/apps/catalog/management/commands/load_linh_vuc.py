"""Load the field-code tree from fixtures/linh_vuc.csv when that file exists."""

import csv

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import DanhMucLinhVuc, HeThongLinhVuc

INSTRUCTION = (
    "Chưa có file fixtures/linh_vuc.csv. Đặt file UTF-8 với các cột "
    "he_thong,ma,ten,cap,ma_cha (ma_cha để trống nếu là nút gốc) rồi chạy lại lệnh. "
    "Các mã lĩnh vực đã có được giữ nguyên."
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
        load_linh_vuc(path, self.stdout)


def load_linh_vuc(path, stdout):
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

    saved = []
    for line_no, row in rows:
        saved.append(_upsert_row(line_no, row))
    for line_no, row, obj in saved:
        _link_parent(line_no, row, obj, stdout)


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
        return line_no, row, obj
    changed = False
    if obj.ten != ten:
        obj.ten = ten
        changed = True
    if obj.cap != cap:
        obj.cap = cap
        changed = True
    if changed:
        obj.save()
    return line_no, row, obj


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
