"""Period choices shared by the preview, exports, and workbook reader."""

from __future__ import annotations

from datetime import date
from zoneinfo import ZoneInfo

from django.utils import timezone

from apps.reporting.rollup import ReportPeriod

ASIA_HO_CHI_MINH = ZoneInfo("Asia/Ho_Chi_Minh")

KIND_MONTH = "month"
KIND_QUARTER = "quarter"
KIND_YEAR = "year"
KIND_CHOICES = (
    (KIND_MONTH, "Tháng"),
    (KIND_QUARTER, "Quý"),
    (KIND_YEAR, "Năm"),
)


def today() -> date:
    """Return the current date in the project's reporting timezone."""
    return timezone.localdate(timezone=ASIA_HO_CHI_MINH)


def resolve_period(
    kind: str,
    year: int,
    *,
    month: int | None = None,
    quarter: int | None = None,
) -> ReportPeriod:
    """Translate a form selection into the ``ReportPeriod`` used by rollup."""
    if kind == KIND_MONTH:
        if month is None:
            raise ValueError("Vui lòng chọn tháng.")
        return ReportPeriod.month(year, month)
    if kind == KIND_QUARTER:
        if quarter is None:
            raise ValueError("Vui lòng chọn quý.")
        return ReportPeriod.quarter(year, quarter)
    if kind == KIND_YEAR:
        return ReportPeriod.annual(year)
    raise ValueError("Loại kỳ báo cáo không hợp lệ.")


def period_label(period: ReportPeriod) -> str:
    if period.kind == KIND_MONTH:
        return f"Tháng {period.start.month}/{period.year}"
    if period.kind == KIND_QUARTER:
        quarter = (period.start.month - 1) // 3 + 1
        return f"Quý {quarter}/{period.year}"
    return f"Năm {period.year}"


def period_slug(period: ReportPeriod) -> str:
    """Return an ASCII-safe period fragment for a file name."""
    if period.kind == KIND_MONTH:
        return f"thang-{period.start.month}-{period.year}"
    if period.kind == KIND_QUARTER:
        quarter = (period.start.month - 1) // 3 + 1
        return f"quy-{quarter}-{period.year}"
    return f"nam-{period.year}"


def months_in_period(period: ReportPeriod) -> list[tuple[int, int]]:
    """Return every (year, month) in the period, in calendar order."""
    months = []
    current = period.start.replace(day=1)
    while current <= period.end:
        months.append((current.year, current.month))
        if current.month == 12:
            current = date(current.year + 1, 1, 1)
        else:
            current = date(current.year, current.month + 1, 1)
    return months
