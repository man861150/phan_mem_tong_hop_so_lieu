"""Presentation helpers for the post-login dashboard.

The underlying indicator values come from :func:`apps.reporting.rollup.rollup`.
This module only groups those results and turns them into chart payloads; it
does not query source tables for business figures.
"""

from __future__ import annotations

from collections import defaultdict
from decimal import Decimal

from apps.catalog.models import PhongBan
from apps.reporting.formatting import format_vi_number
from apps.reporting.rollup import RollupRow

ZERO = Decimal("0")


def mean_percent(rows) -> Decimal | None:
    """Return the equal-weight mean of the non-null rollup percentages.

    Indicators without a confirmed plan have no percent and are omitted from
    the percent chart. Averaging avoids adding indicators that use different
    units.
    """
    values = [row.percent for row in rows if row.percent is not None]
    if not values:
        return None
    return sum(values, ZERO) / Decimal(len(values))


def department_completion(
    rows: list[RollupRow],
    departments: list[PhongBan],
) -> list[dict]:
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.phong_id].append(row)

    points = []
    for department in departments:
        percent = mean_percent(grouped.get(department.pk, []))
        points.append(
            {
                "phong": department,
                "ma_phong": department.ma_phong,
                "ten_phong": department.ten_phong,
                "percent": percent,
                "percent_display": format_vi_number(percent),
            }
        )
    return points


def group_completion(
    rows: list[RollupRow],
    indicators: dict[int, dict],
) -> list[dict]:
    grouped = defaultdict(list)
    labels = {}
    for row in rows:
        info = indicators.get(row.chi_tieu_id)
        if info is None:
            continue
        key = (info["nhom__thu_tu"], info["nhom_id"], info["nhom__ten_mang"])
        grouped[key].append(row)
        labels[key] = info["nhom__ten_mang"]

    points = []
    for key in sorted(grouped):
        percent = mean_percent(grouped[key])
        if percent is None:
            continue
        points.append(
            {
                "ten_mang": labels[key],
                "percent": percent,
                "percent_display": format_vi_number(percent),
            }
        )
    return points


def chart_payload(points: list[dict], label_key: str) -> dict:
    """Return an ECharts-ready payload from completion points.

    Points with no percent are omitted so "chỉ theo dõi" indicators never
    appear in the percent chart.
    """
    comparable = [point for point in points if point["percent"] is not None]
    return {
        "labels": [point[label_key] for point in comparable],
        "values": [float(point["percent"]) for point in comparable],
    }


def cumulative_payload(rows: list[RollupRow]) -> dict:
    """Return the cumulative-versus-plan chart for one department.

    Only indicators with a confirmed plan are comparable. A missing approved
    value is plotted as zero so the year-to-date bar remains readable.
    """
    comparable = [row for row in rows if row.plan is not None]
    return {
        "labels": [row.ten_chi_tieu for row in comparable],
        "codes": [row.ma_chi_tieu for row in comparable],
        "plans": [float(row.plan) for row in comparable],
        "cumulative": [
            float(row.cumulative) if row.cumulative is not None else 0.0
            for row in comparable
        ],
        "units": [row.don_vi_tinh for row in comparable],
    }
