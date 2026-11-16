"""Seed Phòng GDCN from the "6 rõ" workbook.

The workbook is the source of truth. Re-running updates draft plans and
leaves confirmed plans unchanged.
"""

from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass, field
from decimal import Decimal
from pathlib import Path

from django.conf import settings
from django.core.management.base import CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    ChiTieuKeHoach,
    CountSubject,
    DanhMucDoiTuong,
    KieuGhiNhan,
    LoaiHoatDong,
    NguonSoLieu,
    NhomChiTieu,
    PhongBan,
    TrangThaiKeHoach,
)

# Localhost only. Printed by the management command --help.
DEV_PASSWORDS = (
    ("cb.gdcn", "Canbo-local-1"),
    ("ld.gdcn", "Lanhdao-phong-1"),
    ("admin", "Quantri-local-1"),
)

# username, ho_ten, role, ma_phong or None, is_staff, is_superuser
ACCOUNTS = (
    ("cb.gdcn", "Cán bộ GDCN (mẫu)", Role.ENTRY_OFFICER, "GDCN", False, False),
    (
        "ld.gdcn",
        "Lãnh đạo phòng GDCN (mẫu)",
        Role.DEPARTMENT_HEAD,
        "GDCN",
        False,
        False,
    ),
    ("admin", "Quản trị hệ thống", Role.SYSTEM_ADMIN, None, True, True),
)

DEPARTMENT = ("GDCN", "Phòng Giao dịch công nghệ")

# Exact Mảng text → code prefix. An unknown name fails the import.
GROUPS = {
    "Sàn giao dịch công nghệ trực tuyến Techport": "TECHPORT",
    "Xúc tiến chuyển giao công nghệ": "XUCTIEN",
    "Kết nối tư vấn chuyển giao công nghệ": "KETNOI",
    "Lượt tiếp cận và tương tác thông qua vận hành Sàn giao dịch công nghệ": (
        "VANHANH"
    ),
}
MONTH_GROUPS = frozenset({"TECHPORT", "VANHANH"})

# Longer pairs first. Applied to folded tokens before stop-words are dropped.
_BIGRAMS = {
    ("HO", "SO"): "HOSO",
    ("CONG", "NGHE"): "CN",
    ("DAY", "CHUYEN"): "DAYCHUYEN",
    ("THIET", "BI"): "TB",
    ("CHUYEN", "GIA"): "CGIA",
    ("CHUYEN", "GIAO"): "CGIAO",
    ("TU", "VAN"): "TV",
    ("TRI", "TUE"): "TTUE",
    ("DON", "VI"): "DV",
    ("CUNG", "UNG"): "CUNGUNG",
    ("TRUY", "CAP"): "TRUYCAP",
    ("NGUOI", "DUNG"): "USER",
    ("YEU", "CAU"): "YC",
    ("KET", "NOI"): "KN",
    ("CUNG", "CAU"): "CC",
    ("BAI", "VIET"): "BAIVIET",
    ("TRUYEN", "THONG"): "TRUYENTHONG",
    ("TIEP", "CAN"): "TIEPCAN",
    ("TUONG", "TAC"): "TUONGTAC",
    ("GIAO", "DICH"): "GD",
    ("GIAN", "HANG"): "GIANHANG",
    ("HOI", "THAO"): "HOITHAO",
    ("BIEN", "BAN"): "BIENBAN",
    ("TRINH", "DIEN"): "TRINHDIEN",
    ("BAO", "CAO"): "BAOCAO",
    ("THAM", "LUAN"): "THAMLUAN",
    ("TRUNG", "BAY"): "TRUNGBAY",
    ("THAM", "DU"): "THAMDU",
    ("TRUC", "TIEP"): "TRUCTIEP",
    ("TRUC", "TUYEN"): "TRUCTUYEN",
    ("SU", "KIEN"): "SUKIEN",
    ("KHOA", "HOC"): "KH",
    ("TINH", "THANH"): "TINH",
    ("GHI", "NHO"): "GHINHO",
    ("KY", "KET"): "KYKET",
    ("KET", "QUA"): "KQ",
    ("NGHIEN", "CUU"): "NC",
    ("VIEN", "TRUONG"): "VT",
    ("SAN", "PHAM"): "SP",
    ("HOP", "DONG"): "HD",
    ("GIA", "TRI"): "GT",
    ("VAN", "HANH"): "VH",
    ("XUC", "TIEN"): "XT",
    ("HO", "TRO"): "HOTRO",
    ("TRIEN", "LAM"): "TRIENLAM",
    ("HOP", "TAC"): "HOPTAC",
    ("TRIEN", "KHAI"): "TRIENKHAI",
    ("KHA", "NANG"): "KNANG",
    ("GIOI", "THIEU"): "GT",
    ("DANG", "KY"): "DK",
    ("TO", "CHUC"): "TOCHUC",
}
_DROP = frozenset(
    {
        "VA",
        "CAC",
        "CUA",
        "TAI",
        "CHO",
        "LA",
        "THONG",
        "QUA",
        "DUOC",
        "CO",
        "MOT",
        "THEO",
        "TU",
        "VOI",
        "DE",
        "LOAI",
        "TONG",
        "LUONG",
        "LUOT",
        "NAY",
    }
)

_NUMBER = re.compile(r"^(\d+)\s+(\S.*)$")
_BULLET = re.compile(r"^[-–—]\s+(.*\S)\s*$")
_NUMBERED = re.compile(r"(?:^|\n)\s*\d+\.\s*")
_LEADING_SO = re.compile(r"^số\s+", re.IGNORECASE)
_COMPOUND = re.compile(r",\s*(?=số\s)", re.IGNORECASE)
_ASSUMED_CONTRACT_UNIT = "Tổng giá trị hợp đồng"
_CODE_LIMIT = 40

@dataclass
class ChildLine:
    name: str
    value: Decimal | None
    unit: str


@dataclass
class SheetRow:
    rows: list[int]
    stt: int
    group: str
    content: str
    subject: str
    methods: list[str]
    value: Decimal | None
    unit: str
    children: list[ChildLine]
    anchor: tuple[int, int]
    notes: list[str] = field(default_factory=list)


@dataclass
class Indicator:
    name: str
    unit: str
    group_name: str
    group_stt: int
    prefix: str
    parent: Indicator | None
    kieu: str
    cach: str
    count_subject: str
    loai_name: str
    subjects: list[str]
    sources: list[str]
    plans: list[tuple[str | None, Decimal | None]]
    excel_rows: list[int]
    notes: list[str]
    code: str = ""


@dataclass
class SeedPlan:
    indicators: list[Indicator]
    notes: list[str]


def default_workbook() -> Path:
    root = settings.BASE_DIR.parent / "doc"
    matches = sorted(
        path
        for path in root.glob("*GDCN*.xlsx")
        if not path.name.startswith("~$")
    )
    if len(matches) != 1:
        found = ", ".join(path.name for path in matches) or "(không có file)"
        raise CommandError(
            "Cần đúng một workbook GDCN trong doc/. Tìm thấy: " + found
        )
    return matches[0]


def parse_workbook(path: Path) -> SeedPlan:
    """Read the workbook into indicators. Raises CommandError on a bad layout."""
    from openpyxl import load_workbook

    if not path.is_file():
        raise CommandError(f"Không thấy file: {path}")
    workbook = load_workbook(path, data_only=False)
    sheet = workbook[workbook.sheetnames[0]]
    header_row = _header_row(sheet)
    grid, anchors, last_row = _filled_grid(sheet)
    logical = _logical_rows(grid, anchors, header_row, last_row)
    indicators = _indicators_from_rows(logical)
    _assign_codes(indicators)
    notes = [note for indicator in indicators for note in indicator.notes]
    return SeedPlan(indicators=indicators, notes=notes)


def render_plan(plan: SeedPlan, year: int) -> str:
    """Text tree of the import. Safe to print during --dry-run."""
    lines = [f"Năm kế hoạch: {year}", ""]
    grouped: dict[str, list[Indicator]] = {}
    order: list[str] = []
    for indicator in plan.indicators:
        if indicator.group_name not in grouped:
            grouped[indicator.group_name] = []
            order.append(indicator.group_name)
        grouped[indicator.group_name].append(indicator)
    for name in order:
        rows = grouped[name]
        stt = rows[0].group_stt
        lines.append(f"Nhóm {stt}. {name}")
        for indicator in rows:
            if indicator.parent is not None:
                continue
            lines.extend(_render_indicator(indicator, rows, depth=1))
        lines.append("")
    plan_count = sum(len(indicator.plans) for indicator in plan.indicators)
    lines.append(
        f"Tổng: {len(order)} nhóm, {len(plan.indicators)} chỉ tiêu, "
        f"{plan_count} dòng kế hoạch."
    )
    if plan.notes:
        lines.append("")
        lines.append("Ghi chú:")
        lines.extend(f"- {note}" for note in plan.notes)
    return "\n".join(lines)


def apply_seed(plan: SeedPlan, year: int) -> list[str]:
    """Write department, accounts, and catalog rows. Idempotent."""
    with transaction.atomic():
        return _apply(plan, year)


def _apply(plan: SeedPlan, year: int) -> list[str]:
    tally = Counter()
    lines = _ensure_accounts(tally)
    department = PhongBan.objects.get(ma_phong=DEPARTMENT[0])
    groups = _ensure_groups(plan, department, tally)
    subjects = _ensure_named(
        DanhMucDoiTuong,
        "ten_doi_tuong",
        _unique(indicator.subjects for indicator in plan.indicators),
        "doi_tuong",
        tally,
    )
    sources = _ensure_named(
        NguonSoLieu,
        "ten_nguon",
        _unique(indicator.sources for indicator in plan.indicators),
        "nguon",
        tally,
    )
    saved: dict[str, ChiTieu] = {}
    statuses: dict[str, str] = {}
    pending = list(plan.indicators)
    while pending:
        next_pending = []
        progressed = False
        for indicator in pending:
            parent = indicator.parent
            if parent is not None and parent.code not in saved:
                next_pending.append(indicator)
                continue
            saved[indicator.code], status = _ensure_indicator(
                indicator,
                groups[indicator.group_name],
                None if parent is None else saved[parent.code],
                department,
                tally,
            )
            statuses[indicator.code] = status
            progressed = True
        if not progressed:
            raise CommandError("Chỉ tiêu cha không xác định được.")
        pending = next_pending
    for indicator in plan.indicators:
        _ensure_links(
            saved[indicator.code],
            indicator,
            subjects,
            sources,
            statuses[indicator.code],
            tally,
        )
    skipped = []
    for indicator in plan.indicators:
        skipped.extend(
            _ensure_plans(saved[indicator.code], indicator, subjects, year, tally)
        )
    lines.extend(
        [
            (
                f"nhom: tạo {tally['nhom_created']}, "
                f"cập nhật {tally['nhom_updated']}, giữ {tally['nhom_kept']}"
            ),
            (
                f"chi_tieu: tạo {tally['chi_tieu_created']}, "
                f"cập nhật {tally['chi_tieu_updated']}, giữ {tally['chi_tieu_kept']}"
            ),
            (
                f"doi_tuong: tạo {tally['doi_tuong_created']}, "
                f"giữ {tally['doi_tuong_kept']}"
            ),
            (
                f"nguon: tạo {tally['nguon_created']}, giữ {tally['nguon_kept']}"
            ),
            (
                f"loai_hoat_dong: tạo {tally['loai_created']}, "
                f"giữ {tally['loai_kept']}"
            ),
            (
                f"ke_hoach: tạo {tally['ke_hoach_created']}, "
                f"cập nhật {tally['ke_hoach_updated']}, giữ {tally['ke_hoach_kept']}"
            ),
        ]
    )
    if skipped:
        lines.append("Bỏ qua kế hoạch đã xác nhận:")
        lines.extend(f"- {line}" for line in skipped)
    else:
        lines.append("Bỏ qua kế hoạch đã xác nhận: không có.")
    return lines


def _ensure_accounts(tally: Counter) -> list[str]:
    ma_phong, ten_phong = DEPARTMENT
    phong = PhongBan.objects.filter(ma_phong=ma_phong).first()
    created = phong is None
    if created:
        phong = PhongBan(ma_phong=ma_phong)
    if created or phong.ten_phong != ten_phong or not phong.dang_su_dung:
        phong.ten_phong = ten_phong
        phong.dang_su_dung = True
        phong.save()
        state = "created" if created else "updated"
    else:
        state = "kept"
    lines = [f"phong {ma_phong}: {state}"]
    passwords = dict(DEV_PASSWORDS)
    for username, ho_ten, role, account_phong, is_staff, is_superuser in ACCOUNTS:
        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            user = User(username=username)
        desired = phong if account_phong else None
        changed = (
            created
            or user.ho_ten != ho_ten
            or user.email != f"{username}@localhost"
            or user.role != role
            or user.phong_id != getattr(desired, "pk", None)
            or user.is_staff != is_staff
            or user.is_superuser != is_superuser
            or not user.is_active
        )
        password_changed = created or not user.check_password(passwords[username])
        if changed or password_changed:
            user.ho_ten = ho_ten
            user.email = f"{username}@localhost"
            user.role = role
            user.phong = desired
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            if password_changed:
                user.set_password(passwords[username])
            user.save()
            tally[f"user_{'created' if created else 'updated'}"] += 1
            lines.append(f"user {username}: {'created' if created else 'updated'}")
        else:
            lines.append(f"user {username}: kept")
    return lines


def _ensure_groups(plan: SeedPlan, department: PhongBan, tally: Counter):
    groups = {}
    seen = []
    for indicator in plan.indicators:
        if indicator.group_name in groups:
            continue
        seen.append(indicator)
        row = NhomChiTieu.objects.filter(
            phong=department,
            ten_mang=indicator.group_name,
        ).first()
        created = row is None
        if created:
            row = NhomChiTieu(
                phong=department,
                ten_mang=indicator.group_name,
                thu_tu=indicator.group_stt,
            )
            row.save()
            tally["nhom_created"] += 1
        elif row.thu_tu != indicator.group_stt:
            row.thu_tu = indicator.group_stt
            row.save()
            tally["nhom_updated"] += 1
        else:
            tally["nhom_kept"] += 1
        groups[indicator.group_name] = row
    return groups


def _ensure_named(model, field_name, names, tally_key, tally: Counter):
    found = {}
    for name in names:
        if len(name) > 255:
            raise CommandError(f"{field_name} dài hơn 255 ký tự: {name}")
        row = model.objects.filter(**{field_name: name}).first()
        if row is None:
            row = model(**{field_name: name})
            row.save()
            tally[f"{tally_key}_created"] += 1
        else:
            tally[f"{tally_key}_kept"] += 1
        found[name] = row
    return found


def _ensure_indicator(indicator, group, parent, department, tally: Counter):
    """Create or update one indicator. Returns the row and kept/updated/created."""
    loai = None
    if indicator.loai_name:
        loai = LoaiHoatDong.objects.filter(
            phong=department,
            ten_loai=indicator.loai_name,
        ).first()
        if loai is None:
            loai = LoaiHoatDong(
                phong=department,
                ten_loai=indicator.loai_name,
                co_ke_hoach_so_luong=True,
            )
            loai.save()
            tally["loai_created"] += 1
        else:
            tally["loai_kept"] += 1
    values = {
        "ten_chi_tieu": indicator.name,
        "don_vi_tinh": indicator.unit,
        "nhom": group,
        "chi_tieu_cha": parent,
        "kieu_ghi_nhan": indicator.kieu,
        "cach_tong_hop": indicator.cach,
        "count_subject": indicator.count_subject,
        "loai_hoat_dong": loai,
        "phan_loai_doi_tuong": bool(indicator.subjects),
    }
    row = ChiTieu.objects.filter(ma_chi_tieu=indicator.code).first()
    created = row is None
    if created:
        row = ChiTieu(ma_chi_tieu=indicator.code, **values)
        row.save()
        tally["chi_tieu_created"] += 1
        return row, "created"
    changed = False
    for key, value in values.items():
        current = getattr(row, key)
        if current != value:
            setattr(row, key, value)
            changed = True
    if changed:
        row.save()
        tally["chi_tieu_updated"] += 1
        return row, "updated"
    tally["chi_tieu_kept"] += 1
    return row, "kept"


def _ensure_links(row, indicator, subjects, sources, status: str, tally: Counter):
    subject_rows = [subjects[name] for name in indicator.subjects]
    source_rows = [sources[name] for name in indicator.sources]
    changed = _replace_m2m(row.doi_tuong_ap_dung, subject_rows)
    changed = _replace_m2m(row.nguon_cho_phep, source_rows) or changed
    if changed and status == "kept":
        tally["chi_tieu_kept"] -= 1
        tally["chi_tieu_updated"] += 1


def _replace_m2m(relation, rows) -> bool:
    current = set(relation.values_list("pk", flat=True))
    desired = {row.pk for row in rows}
    if current == desired:
        return False
    relation.set(rows)
    return True


def _ensure_plans(row, indicator, subjects, year, tally: Counter) -> list[str]:
    skipped = []
    for subject_name, value in indicator.plans:
        subject = None if subject_name is None else subjects[subject_name]
        existing = ChiTieuKeHoach.objects.filter(
            chi_tieu=row,
            nam=year,
            doi_tuong=subject,
        ).first()
        label = indicator.code if subject is None else f"{indicator.code} / {subject_name}"
        if existing is None:
            ChiTieuKeHoach(
                chi_tieu=row,
                nam=year,
                doi_tuong=subject,
                gia_tri_ke_hoach=value,
                trang_thai=TrangThaiKeHoach.DU_THAO,
            ).save()
            tally["ke_hoach_created"] += 1
            continue
        if existing.trang_thai == TrangThaiKeHoach.DA_XAC_NHAN:
            if not _same_decimal(existing.gia_tri_ke_hoach, value):
                skipped.append(
                    f"{label}: giữ {existing.gia_tri_ke_hoach}, workbook có {value}"
                )
            tally["ke_hoach_kept"] += 1
            continue
        if _same_decimal(existing.gia_tri_ke_hoach, value):
            tally["ke_hoach_kept"] += 1
            continue
        existing.gia_tri_ke_hoach = value
        existing.save()
        tally["ke_hoach_updated"] += 1
    return skipped


def _header_row(sheet) -> int:
    for row_number in range(1, 16):
        values = [_plain(sheet.cell(row_number, column).value) for column in range(1, 7)]
        if values[:3] == ["STT", "Mảng", "Nội dung"] and values[4:] == [
            "Phương pháp thu thập",
            "Số lượng chỉ tiêu",
        ]:
            return row_number
    raise CommandError(
        "Không thấy header STT | Mảng | Nội dung | Phương pháp thu thập | "
        "Số lượng chỉ tiêu trong 15 dòng đầu."
    )


def _filled_grid(sheet):
    last = 1
    grid = {}
    for row in sheet.iter_rows(
        min_row=1,
        max_row=sheet.max_row,
        max_col=6,
    ):
        for cell in row:
            grid[(cell.row, cell.column)] = cell.value
            if cell.value not in (None, ""):
                last = max(last, cell.row)
    anchors = {}
    for merged in sheet.merged_cells.ranges:
        anchor = (merged.min_row, merged.min_col)
        value = grid.get(anchor)
        for row_number in range(merged.min_row, merged.max_row + 1):
            for column in range(merged.min_col, merged.max_col + 1):
                if column <= 6:
                    grid[(row_number, column)] = value
                    if column == 6:
                        anchors[(row_number, 6)] = anchor
                    if value not in (None, ""):
                        last = max(last, row_number)
    return grid, anchors, last


def _logical_rows(grid, anchor_map, header_row, last) -> list[SheetRow]:
    logical: list[SheetRow] = []
    for row_number in range(header_row + 1, last + 1):
        raw = [_plain(grid.get((row_number, column))) for column in range(1, 7)]
        if not any(raw):
            continue
        stt_text, group, content, subject, method, quantity = raw
        if group not in GROUPS:
            raise CommandError(
                f"Dòng {row_number}: mảng không thuộc 4 nhóm đã biết: {group!r}"
            )
        try:
            stt = int(stt_text)
        except ValueError as exc:
            raise CommandError(f"Dòng {row_number}: STT không phải số: {stt_text!r}") from exc
        methods, method_notes = _methods(method, row_number)
        value, unit, children, quantity_notes = _quantity(quantity, content, row_number)
        anchor = anchor_map.get((row_number, 6), (row_number, 6))
        current = SheetRow(
            rows=[row_number],
            stt=stt,
            group=group,
            content=content,
            subject=subject,
            methods=methods,
            value=value,
            unit=unit,
            children=children,
            anchor=anchor,
            notes=method_notes + quantity_notes,
        )
        if logical and _same_row(logical[-1], current):
            logical[-1].rows.append(row_number)
            continue
        logical.append(current)
    if not logical:
        raise CommandError("Workbook không có dòng dữ liệu dưới header.")
    return logical


def _same_row(left: SheetRow, right: SheetRow) -> bool:
    return (
        left.stt == right.stt
        and left.group == right.group
        and left.content == right.content
        and left.subject == right.subject
        and left.methods == right.methods
        and left.value == right.value
        and left.unit == right.unit
        and [(item.name, item.value, item.unit) for item in left.children]
        == [(item.name, item.value, item.unit) for item in right.children]
        and left.anchor == right.anchor
    )


def _indicators_from_rows(rows: list[SheetRow]) -> list[Indicator]:
    blocks: list[list[SheetRow]] = []
    for row in rows:
        key = (row.stt, row.group, row.content)
        if blocks and (blocks[-1][0].stt, blocks[-1][0].group, blocks[-1][0].content) == key:
            blocks[-1].append(row)
        else:
            blocks.append([row])
    indicators = []
    for block in blocks:
        indicators.extend(_indicators_from_block(block))
    return indicators


def _indicators_from_block(block: list[SheetRow]) -> list[Indicator]:
    subjects = [row.subject for row in block]
    if any(subjects) and not all(subjects):
        raise CommandError(
            f"Dòng {_span(block[0])}: cùng nội dung nhưng có dòng thiếu cột đối tượng."
        )
    if not any(subjects):
        if len(block) != 1:
            raise CommandError(
                f"Dòng {_span(block[0])}: nội dung lặp mà không có cột đối tượng."
            )
        return _family(block[0], block[0].content or block[0].group, block[0].notes)
    units = {row.unit for row in block}
    if len(units) == 1 and block[0].unit:
        return _subject_family(block)
    note = (
        f"Dòng {block[0].rows[0]}–{block[-1].rows[-1]}: cột phạm vi có đơn vị khác nhau "
        f"({', '.join(sorted(units))}). Mỗi dòng là một chỉ tiêu, không tạo đối tượng."
    )
    built = []
    for index, row in enumerate(block):
        name = f"{row.content} — {row.subject}"
        extra = [note] if index == 0 else []
        built.extend(_family(row, name, row.notes + extra))
    return built


def _family(row: SheetRow, name: str, notes: list[str]) -> list[Indicator]:
    parent = _make_indicator(
        name=name,
        unit=row.unit,
        row=row,
        subjects=[],
        sources=list(row.methods),
        plans=[(None, row.value)],
        notes=list(notes),
        excel_rows=list(row.rows),
        parent=None,
    )
    children = [
        _make_indicator(
            name=child.name,
            unit=child.unit,
            row=row,
            subjects=[],
            sources=list(row.methods),
            plans=[(None, child.value)],
            notes=[],
            excel_rows=list(row.rows),
            parent=parent,
        )
        for child in row.children
    ]
    return [parent, *children]


def _subject_family(block: list[SheetRow]) -> list[Indicator]:
    first = block[0]
    child_keys = {
        tuple((child.name, child.value, child.unit) for child in row.children)
        for row in block
    }
    if len(child_keys) != 1:
        raise CommandError(
            f"Dòng {_span(first)}: các đối tượng của cùng nội dung có danh sách con khác nhau."
        )
    anchors = {row.anchor for row in block}
    values = {row.value for row in block}
    notes = [note for row in block for note in row.notes]
    subject_names = [row.subject for row in block]
    if len(anchors) == 1:
        if len(values) != 1:
            raise CommandError(
                f"Dòng {_span(first)}: một ô số lượng gộp nhưng các giá trị khác nhau."
            )
        plans = [(None, first.value)]
        notes.append(
            "Dòng "
            f"{first.rows[0]}–{block[-1].rows[-1]}: ô số lượng gộp thành một kế hoạch "
            f"{_plain_value(first.value)} {first.unit}. Đối tượng gắn vào chỉ tiêu, "
            "không tách thành từng kế hoạch."
        )
    else:
        plans = [(row.subject, row.value) for row in block]
    parent = _make_indicator(
        name=first.content,
        unit=first.unit,
        row=first,
        subjects=subject_names,
        sources=_union(row.methods for row in block),
        plans=plans,
        notes=notes,
        excel_rows=[number for row in block for number in row.rows],
        parent=None,
    )
    children = [
        _make_indicator(
            name=child.name,
            unit=child.unit,
            row=first,
            subjects=[],
            sources=list(parent.sources),
            plans=[(None, child.value)],
            notes=[],
            excel_rows=list(parent.excel_rows),
            parent=parent,
        )
        for child in first.children
    ]
    return [parent, *children]


def _make_indicator(
    *,
    name,
    unit,
    row,
    subjects,
    sources,
    plans,
    notes,
    excel_rows,
    parent,
) -> Indicator:
    if not name:
        raise CommandError(f"Dòng {_span(row)}: thiếu tên chỉ tiêu.")
    if len(name) > 255:
        raise CommandError(f"Dòng {_span(row)}: tên chỉ tiêu dài hơn 255 ký tự.")
    if not unit or len(unit) > 50:
        raise CommandError(
            f"Dòng {_span(row)}: đơn vị tính trống hoặc dài hơn 50 ký tự ({unit!r})."
        )
    prefix = GROUPS[row.group]
    kieu, cach, count_subject, loai_name = _modes(name, unit, prefix)
    return Indicator(
        name=name,
        unit=unit,
        group_name=row.group,
        group_stt=row.stt,
        prefix=prefix,
        parent=parent,
        kieu=kieu,
        cach=cach,
        count_subject=count_subject,
        loai_name=loai_name,
        subjects=subjects,
        sources=sources,
        plans=plans,
        excel_rows=excel_rows,
        notes=notes,
    )


def _modes(name: str, unit: str, prefix: str):
    if unit == "sự kiện":
        return (
            KieuGhiNhan.ACTIVITY,
            CachTongHop.COUNT,
            CountSubject.ACTIVITY,
            name,
        )
    folded = f"{name} {unit}".casefold()
    if "tiếp cận" in folded or "tương tác" in folded:
        return KieuGhiNhan.MONTH, CachTongHop.CUMULATIVE, "", ""
    kieu = KieuGhiNhan.MONTH if prefix in MONTH_GROUPS else KieuGhiNhan.ACTIVITY
    return kieu, CachTongHop.SUM, "", ""


def _methods(text: str, row_number: int) -> tuple[list[str], list[str]]:
    if not text:
        return [], []
    original = text
    unwrapped = text
    if text.startswith('"') and text.endswith('"'):
        inner = text[1:-1].strip()
        if re.match(r"\d+\.", inner):
            unwrapped = inner
    parts = [part for part in _NUMBERED.split(unwrapped) if part.strip()]
    if not parts:
        parts = [unwrapped]
    cleaned = []
    changed = unwrapped != original
    for part in parts:
        item = re.sub(r"\s+", " ", part).strip()
        balanced = _balance_quotes(item)
        if balanced != item:
            changed = True
        if balanced.count('"') % 2:
            raise CommandError(
                f"Dòng {row_number}: không cân được ngoặc kép trong {balanced!r}"
            )
        if len(balanced) > 255:
            raise CommandError(
                f"Dòng {row_number}: nguồn số liệu dài hơn 255 ký tự."
            )
        cleaned.append(balanced)
    notes = []
    if changed:
        notes.append(
            f"Dòng {row_number}: đã sửa ngoặc kép ở phương pháp thu thập, chữ giữ nguyên."
        )
    return cleaned, notes


def _balance_quotes(text: str) -> str:
    while text.count('"') % 2:
        if text.startswith('"') and not text.endswith('"'):
            text = text[1:].strip()
            continue
        if text.endswith('"') and not text.startswith('"'):
            text = text[:-1].strip()
            continue
        return text + '"'
    return text


def _quantity(text: str, content: str, row_number: int):
    notes = []
    if not text:
        if content != _ASSUMED_CONTRACT_UNIT:
            raise CommandError(
                f"Dòng {row_number}: ô số lượng trống và không có quy tắc đơn vị."
            )
        notes.append(
            "Dòng "
            f"{row_number}: ô số lượng trống. Đơn vị giả định \"đồng\", "
            "giá trị kế hoạch trống."
        )
        return None, "đồng", [], notes
    lines = [line.strip() for line in text.split("\n") if line.strip()]
    value, unit = _head(lines[0], row_number)
    children = []
    for line in lines[1:]:
        match = _BULLET.match(line)
        if match is None:
            raise CommandError(
                f"Dòng {row_number}: dòng con không bắt đầu bằng gạch: {line!r}"
            )
        for piece in _split_compound(match.group(1), row_number, notes):
            children.append(_child(piece, row_number))
    return value, unit, children, notes


def _head(line: str, row_number: int) -> tuple[Decimal | None, str]:
    match = _NUMBER.match(line)
    if match:
        unit = re.sub(r"\s+", " ", match.group(2)).strip()
        _check_unit(unit, row_number)
        return Decimal(match.group(1)), unit
    if re.match(r"^\d", line):
        raise CommandError(f"Dòng {row_number}: không đọc được số lượng {line!r}")
    unit = re.sub(r"\s+", " ", line).strip()
    _check_unit(unit, row_number)
    return None, unit


def _child(piece: str, row_number: int) -> ChildLine:
    match = _NUMBER.match(piece)
    if match:
        unit = re.sub(r"\s+", " ", match.group(2)).strip()
        _check_unit(unit, row_number)
        return ChildLine(piece, Decimal(match.group(1)), unit)
    unit = _LEADING_SO.sub("", piece).strip()
    unit = re.sub(r"\s+", " ", unit)
    _check_unit(unit, row_number)
    return ChildLine(piece, None, unit)


def _split_compound(piece: str, row_number: int, notes: list[str]) -> list[str]:
    parts = [part.strip() for part in _COMPOUND.split(piece) if part.strip()]
    if len(parts) > 1:
        notes.append(
            f"Dòng {row_number}: gạch đầu dòng {piece!r} tách thành {len(parts)} chỉ tiêu con."
        )
    return parts


def _check_unit(unit: str, row_number: int) -> None:
    if not unit or len(unit) > 50:
        raise CommandError(
            f"Dòng {row_number}: đơn vị tính trống hoặc dài hơn 50 ký tự ({unit!r})."
        )


def _assign_codes(indicators: list[Indicator]) -> None:
    used: dict[str, str] = {}
    for indicator in indicators:
        prefix = f"GDCN-{indicator.prefix}-"
        own = _tokens(indicator.name)
        if indicator.parent is None:
            body = _fit(own, _CODE_LIMIT - len(prefix))
            code = prefix + body
        else:
            parent_tokens = _tokens(indicator.parent.name)
            code = _fit_child(prefix, parent_tokens, own)
        if code in used:
            raise CommandError(
                f"Mã {code} trùng giữa {used[code]!r} và {indicator.name!r}."
            )
        if len(code) > _CODE_LIMIT:
            raise CommandError(f"Mã dài hơn {_CODE_LIMIT} ký tự: {code}")
        indicator.code = code
        used[code] = indicator.name


def _tokens(text: str) -> list[str]:
    folded = unicodedata.normalize("NFC", text).replace("Đ", "D").replace("đ", "d")
    folded = unicodedata.normalize("NFD", folded)
    folded = "".join(
        char for char in folded if unicodedata.category(char) != "Mn"
    )
    folded = folded.upper().replace("&", " ")
    raw = re.sub(r"[^A-Z0-9]+", " ", folded).split()
    tokens = []
    index = 0
    while index < len(raw):
        pair = (raw[index], raw[index + 1]) if index + 1 < len(raw) else None
        if pair in _BIGRAMS:
            tokens.append(_BIGRAMS[pair])
            index += 2
            continue
        tokens.append(raw[index])
        index += 1
    if len(tokens) >= 3 and tokens[0] == "TAI" and tokens[1] == "SAN" and tokens[2] == "TTUE":
        tokens = ["TSAN", *tokens[2:]]
    elif (
        len(tokens) >= 3
        and tokens[0] != "TAI"
        and "TAI" in tokens
    ):
        rebuilt = []
        index = 0
        while index < len(tokens):
            if (
                index + 2 < len(tokens)
                and tokens[index] == "TAI"
                and tokens[index + 1] == "SAN"
                and tokens[index + 2] == "TTUE"
            ):
                rebuilt.append("TSAN")
                index += 2
                continue
            rebuilt.append(tokens[index])
            index += 1
        tokens = rebuilt
    if tokens and tokens[0] == "SO":
        tokens = tokens[1:]
    tokens = [token for token in tokens if token not in _DROP]
    collapsed = []
    for token in tokens:
        if collapsed and collapsed[-1] == token:
            continue
        if collapsed and collapsed[-1] == "CN" and token == "TB":
            collapsed[-1] = "CNTB"
            continue
        collapsed.append(token)
    return collapsed or ["CT"]


def _fit(tokens: list[str], limit: int) -> str:
    """Keep the first tokens and drop filler in the middle until the code fits."""
    kept = list(tokens)
    while len("-".join(kept)) > limit and len(kept) > 2:
        kept.pop(2 if len(kept) > 2 else -1)
    body = "-".join(kept)
    if len(body) > limit and len(kept) == 2:
        body = kept[0]
    if len(body) > limit:
        raise CommandError(f"Không rút được mã trong {limit} ký tự từ {tokens}.")
    return body


def _parent_key(tokens: list[str]) -> list[str]:
    if len(tokens) >= 2 and len("-".join(tokens[-2:])) <= 16:
        return tokens[-2:]
    return tokens[-1:]


def _fit_child(prefix: str, parent_tokens: list[str], own_tokens: list[str]) -> str:
    parent = _parent_key(parent_tokens)
    own = list(own_tokens)
    while True:
        body = "-".join([*parent, *own])
        if len(prefix) + len(body) <= _CODE_LIMIT:
            return prefix + body
        if len(own) > 3:
            own.pop(2)
            continue
        if len(own) == 3:
            own.pop(1)
            continue
        if len(parent) > 1:
            parent = parent[-1:]
            continue
        if len(own) > 1:
            own.pop(0)
            continue
        raise CommandError(
            "Không rút được mã chỉ tiêu con trong "
            f"{_CODE_LIMIT} ký tự: {prefix}{body}"
        )


def _render_indicator(indicator: Indicator, rows: list[Indicator], depth: int) -> list[str]:
    pad = "  " * depth
    plan_text = "; ".join(_format_plan(subject, value) for subject, value in indicator.plans)
    lines = [
        f"{pad}{indicator.name}",
        f"{pad}  mã: {indicator.code}",
        f"{pad}  dòng Excel: {_row_span(indicator.excel_rows)}",
        f"{pad}  kiểu: {indicator.kieu} / {indicator.cach}",
        f"{pad}  đơn vị: {indicator.unit}",
        f"{pad}  kế hoạch: {plan_text}",
    ]
    if indicator.subjects:
        lines.append(f"{pad}  đối tượng: {', '.join(indicator.subjects)}")
    if indicator.sources:
        lines.append(f"{pad}  nguồn: {'; '.join(indicator.sources)}")
    if indicator.loai_name:
        lines.append(f"{pad}  loại hoạt động: {indicator.loai_name}")
    for child in rows:
        if child.parent is indicator:
            lines.extend(_render_indicator(child, rows, depth + 1))
    return lines


def _format_plan(subject: str | None, value: Decimal | None) -> str:
    shown = "trống" if value is None else _plain_value(value)
    if subject is None:
        return shown
    return f"{subject}: {shown}"


def _plain_value(value: Decimal | None) -> str:
    if value is None:
        return "trống"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _plain(value) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    if isinstance(value, int) and not isinstance(value, bool):
        text = str(value)
    else:
        text = str(value)
    text = unicodedata.normalize("NFC", text.replace("\r\n", "\n").replace("\r", "\n"))
    return text.strip()


def _span(row: SheetRow) -> str:
    return _row_span(row.rows)


def _row_span(rows: list[int]) -> str:
    if not rows:
        return "?"
    if rows[0] == rows[-1]:
        return str(rows[0])
    return f"{rows[0]}-{rows[-1]}"


def _union(groups) -> list[str]:
    seen = []
    for group in groups:
        for name in group:
            if name not in seen:
                seen.append(name)
    return seen


def _unique(groups) -> list[str]:
    return _union(groups)


def _same_decimal(left, right) -> bool:
    if left is None or right is None:
        return left is None and right is None
    return Decimal(left) == Decimal(right)
