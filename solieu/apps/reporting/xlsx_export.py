"""Build the periodic report workbook with numeric Excel cells."""

from __future__ import annotations

from decimal import Decimal
from io import BytesIO

from openpyxl import Workbook, load_workbook
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

from apps.reporting.report_data import GAP_NOTE, DepartmentReport

HEADERS = (
    "Chỉ tiêu",
    "Đơn vị tính",
    "Kế hoạch năm",
    "Thực hiện trong kỳ",
    "Lũy kế",
    "% hoàn thành",
    "Ghi chú",
)
DANH_GIA_HEADER = "Đánh giá hiệu quả"
NUMBER_FORMAT = "#,##0.##"
NUMBER_STEP = Decimal("0.0001")
SECTION_FILL = PatternFill("solid", fgColor="D9E7F4")
HEADER_FILL = PatternFill("solid", fgColor="1F4E78")
THIN = Side(style="thin", color="B7C9D6")
BORDER = Border(left=THIN, right=THIN, top=THIN, bottom=THIN)


class ExcelPrecisionError(Exception):
    """A Decimal that an Excel numeric cell would store differently."""

    def __init__(self, value, name, stored):
        self.value = value
        self.name = name
        self.stored = stored
        super().__init__(
            "Không xuất được vì số "
            f"{_format_decimal(value)} của chỉ tiêu {name} không giữ được "
            f"trong ô Excel (ô sẽ lưu {_format_decimal(stored)})."
        )


def _format_decimal(value):
    """Render a Decimal without trailing zeros."""
    text = format(Decimal(value).normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _quantize(value):
    return Decimal(value).quantize(NUMBER_STEP)


def _stored_excel_value(value):
    """Write one number to an in-memory workbook and read the cell back."""
    workbook = Workbook()
    workbook.active["A1"] = float(value)
    output = BytesIO()
    workbook.save(output)
    output.seek(0)
    read_back = load_workbook(output, read_only=True, data_only=True)
    try:
        stored = read_back.active["A1"].value
    finally:
        read_back.close()
    if stored is None:
        raise ExcelPrecisionError(
            _quantize(value),
            "",
            _quantize(value),
        )
    return _quantize(Decimal(str(stored)))


def check_number_precision(value, name):
    """Raise when the numeric cell cannot hold the quantized Decimal.

    This is judged by the file, not by a digit count: 16 significant digits
    can survive while 17 cannot.  Returns the value the cell will store.
    """
    if value is None:
        return None
    original = _quantize(value)
    stored = _stored_excel_value(original)
    if stored != original:
        raise ExcelPrecisionError(original, name, stored)
    return stored


def _check_report_numbers(reports: list[DepartmentReport]) -> None:
    for report in reports:
        for row in report.rows:
            for value in (
                row.plan,
                row.period_value,
                row.cumulative,
                row.percent,
            ):
                check_number_precision(value, row.ten_chi_tieu)


def _number(value):
    """Excel must receive a number, never a Vietnamese formatted string."""
    if value is None:
        return None
    return float(value)


def _headers_for(reports: list[DepartmentReport]) -> tuple[str, ...]:
    if any(report.phong.ma_phong == "TTTK" for report in reports):
        return (*HEADERS, DANH_GIA_HEADER)
    return HEADERS


def build_workbook(
    reports: list[DepartmentReport],
    *,
    period_label: str,
    accepted: bool,
) -> bytes:
    _check_report_numbers(reports)
    headers = _headers_for(reports)
    column_count = len(headers)
    workbook = Workbook()
    sheet = workbook.active
    sheet.title = "Báo cáo"
    sheet.freeze_panes = "A2"
    sheet.sheet_view.showGridLines = True
    workbook.properties.title = f"Báo cáo tổng hợp — {period_label}"
    workbook.properties.subject = period_label

    sheet.append(headers)
    for index in range(1, column_count + 1):
        cell = sheet.cell(row=1, column=index)
        cell.font = Font(bold=True, color="FFFFFF")
        cell.fill = HEADER_FILL
        cell.alignment = Alignment(horizontal="center", vertical="center", wrap_text=True)
        cell.border = BORDER
    sheet.row_dimensions[1].height = 32

    for report in reports:
        section_row = sheet.max_row + 1
        sheet.cell(
            row=section_row,
            column=1,
            value=f"PHÒNG {report.ma_phong} — {report.ten}",
        )
        sheet.merge_cells(
            start_row=section_row,
            start_column=1,
            end_row=section_row,
            end_column=column_count,
        )
        section_cell = sheet.cell(row=section_row, column=1)
        section_cell.font = Font(bold=True)
        section_cell.fill = SECTION_FILL
        section_cell.border = BORDER
        sheet.row_dimensions[section_row].height = 22

        for row in report.rows:
            note = (
                GAP_NOTE
                if accepted and row.chi_tieu_id in report.affected_ids
                else ""
            )
            values = [
                row.ten_chi_tieu,
                row.don_vi_tinh,
                _number(row.plan),
                _number(row.period_value),
                _number(row.cumulative),
                _number(row.percent),
                note,
            ]
            if column_count == 8:
                values.append(report.notes.get(row.chi_tieu_id, ""))
            sheet.append(values)
            current = sheet.max_row
            for column in (3, 4, 5, 6):
                cell = sheet.cell(row=current, column=column)
                cell.number_format = NUMBER_FORMAT
                cell.alignment = Alignment(horizontal="right")
            for column in range(1, column_count + 1):
                sheet.cell(row=current, column=column).border = BORDER
            sheet.cell(row=current, column=1).alignment = Alignment(
                wrap_text=True,
                vertical="top",
            )
            sheet.cell(row=current, column=column_count).alignment = Alignment(
                wrap_text=True,
                vertical="top",
            )

    widths = (52, 16, 16, 18, 14, 14, 28)
    for index, width in enumerate(widths, start=1):
        sheet.column_dimensions[get_column_letter(index)].width = width
    if column_count == 8:
        sheet.column_dimensions[get_column_letter(8)].width = 36

    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
