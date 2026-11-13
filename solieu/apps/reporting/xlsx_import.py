"""Read a workbook written by :mod:`apps.reporting.xlsx_export`."""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from zipfile import BadZipFile, ZipFile

from openpyxl import load_workbook
from openpyxl.utils.exceptions import InvalidFileException

from apps.reporting.formatting import format_vi_number
from apps.reporting.xlsx_export import DANH_GIA_HEADER, HEADERS

HEADER_ERROR = "Tệp Excel không đúng mẫu báo cáo."
ZIP_LIMIT_ERROR = (
    "Tệp Excel có quá nhiều thành phần hoặc nội dung giải nén "
    "vượt quá giới hạn."
)
MAX_ZIP_ENTRIES = 64
MAX_ZIP_UNCOMPRESSED_BYTES = 32 * 1024 * 1024


class WorkbookFormatError(ValueError):
    """The uploaded workbook is not a periodic report."""


@dataclass
class ImportedRow:
    section: str
    chi_tieu: str
    don_vi_tinh: str
    ke_hoach: str
    thuc_hien: str
    luy_ke: str
    phan_tram: str
    ghi_chu: str
    danh_gia: str


def _text(value) -> str:
    if value is None:
        return ""
    return str(value).strip()


def _decimal(value) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    if isinstance(value, (int, float)):
        return Decimal(str(value))
    text = _text(value)
    if text in ("", "—", "-"):
        return None
    if "," in text:
        text = text.replace(".", "").replace(",", ".")
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def _display(value) -> str:
    return format_vi_number(_decimal(value))


def _normalised_headers(values) -> tuple[str, ...]:
    headers = [_text(value) for value in values]
    while headers and not headers[-1]:
        headers.pop()
    return tuple(headers)


def _check_zip_limits(uploaded_file) -> None:
    """Reject oversized ZIP metadata before openpyxl reads any cell."""
    too_large = False
    try:
        uploaded_file.seek(0)
        with ZipFile(uploaded_file) as archive:
            entries = archive.infolist()
            too_large = len(entries) > MAX_ZIP_ENTRIES or (
                sum(info.file_size for info in entries)
                > MAX_ZIP_UNCOMPRESSED_BYTES
            )
    except (BadZipFile, OSError, ValueError):
        return
    finally:
        try:
            uploaded_file.seek(0)
        except (AttributeError, OSError):
            pass
    if too_large:
        raise WorkbookFormatError(ZIP_LIMIT_ERROR)


def parse_workbook(uploaded_file) -> tuple[list[ImportedRow], int]:
    """Return parsed preview rows and the workbook's column count.

    The preview is read-only. No database row is created or approved here.
    """
    _check_zip_limits(uploaded_file)
    try:
        workbook = load_workbook(
            uploaded_file,
            read_only=True,
            data_only=True,
        )
    except (
        BadZipFile,
        InvalidFileException,
        OSError,
        ValueError,
        KeyError,
    ) as exc:
        raise WorkbookFormatError(HEADER_ERROR) from exc

    sheet = workbook.active
    if sheet is None:
        workbook.close()
        raise WorkbookFormatError(HEADER_ERROR)
    rows = sheet.iter_rows(values_only=True)
    try:
        first_row = next(rows)
    except StopIteration as exc:
        raise WorkbookFormatError(HEADER_ERROR) from exc

    headers = _normalised_headers(first_row)
    valid_headers = (HEADERS, (*HEADERS, DANH_GIA_HEADER))
    if headers not in valid_headers:
        workbook.close()
        raise WorkbookFormatError(HEADER_ERROR)

    column_count = len(headers)
    has_danh_gia = column_count == len(HEADERS) + 1
    section = ""
    imported = []
    for values in rows:
        padded = list(values) + [None] * max(0, column_count - len(values))
        padded = padded[:column_count]
        if not any(_text(value) for value in padded):
            continue
        first = _text(padded[0])
        if first.startswith("PHÒNG ") and not any(
            _text(value) for value in padded[1:]
        ):
            section = first
            continue
        imported.append(
            ImportedRow(
                section=section,
                chi_tieu=first,
                don_vi_tinh=_text(padded[1]),
                ke_hoach=_display(padded[2]),
                thuc_hien=_display(padded[3]),
                luy_ke=_display(padded[4]),
                phan_tram=_display(padded[5]),
                ghi_chu=_text(padded[6]),
                danh_gia=_text(padded[7]) if has_danh_gia else "",
            )
        )
    workbook.close()
    return imported, column_count
