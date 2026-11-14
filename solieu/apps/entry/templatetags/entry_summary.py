"""Presentation counts for the reporting-period chooser.

The chooser already receives one row per period. These filters keep the
summary strip accurate without adding queries or changing the view.
"""

from django import template

from apps.entry.models import TrangThaiPhieu

register = template.Library()

_UNSUBMITTED = frozenset({TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI})


@register.filter
def period_count(rows, kind):
    """Count rows by period or report state for the summary strip."""
    rows = rows or ()
    if kind == "open":
        return sum(1 for row in rows if row.get("is_open"))
    if kind == "closed":
        return sum(1 for row in rows if not row.get("is_open"))
    if kind == "attention":
        return sum(
            1
            for row in rows
            if row.get("is_open")
            and (
                row.get("phieu") is None
                or row["phieu"].trang_thai in _UNSUBMITTED
            )
        )
    if kind == "approved":
        return sum(
            1
            for row in rows
            if row.get("phieu") is not None
            and row["phieu"].trang_thai == TrangThaiPhieu.DA_DUYET
        )
    return 0
