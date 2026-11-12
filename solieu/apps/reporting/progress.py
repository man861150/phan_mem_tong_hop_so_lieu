"""Progress-table grouping and drill-down source rows.

The displayed totals remain the values on :class:`RollupRow`. The drill-down
uses the same attribution and approval filters as ``rollup`` so the approved
rows listed on the detail page are the rows that produced the total.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date

from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    CountSubject,
    PhongBan,
)
from apps.entry.models import LoaiPhieu
from apps.reporting.formatting import format_vi_number
from apps.reporting.rollup import (
    OFFICIAL_STATUS,
    ReportPeriod,
    RollupRow,
    _activity_count_queryset,
    _project_count_queryset,
    _solieu_queryset,
)


def build_progress_groups(
    rows: list[RollupRow],
    departments: list[PhongBan],
    *,
    include_pending: bool,
) -> list[dict]:
    """Group rollup rows by department and mảng for the progress table."""
    indicator_ids = {row.chi_tieu_id for row in rows}
    indicators = {
        item["pk"]: item
        for item in ChiTieu.objects.filter(pk__in=indicator_ids).values(
            "pk",
            "nhom_id",
            "nhom__ten_mang",
            "nhom__thu_tu",
        )
    }
    rows_by_department = defaultdict(list)
    for row in rows:
        rows_by_department[row.phong_id].append(row)

    department_blocks = []
    for department in departments:
        grouped = defaultdict(list)
        for row in rows_by_department.get(department.pk, []):
            info = indicators.get(row.chi_tieu_id)
            if info is None:
                continue
            key = (
                info["nhom__thu_tu"],
                info["nhom_id"],
                info["nhom__ten_mang"],
            )
            grouped[key].append(
                {
                    "chi_tieu_id": row.chi_tieu_id,
                    "ma_chi_tieu": row.ma_chi_tieu,
                    "ten_chi_tieu": row.ten_chi_tieu,
                    "don_vi_tinh": row.don_vi_tinh,
                    "plan": format_vi_number(row.plan),
                    "cumulative": format_vi_number(row.cumulative),
                    "percent": format_vi_number(row.percent),
                    "remainder": format_vi_number(row.remainder),
                    "pending": format_vi_number(row.pending_cumulative),
                    "behind": row.behind,
                    "only_track": row.plan is None,
                    "percent_missing": row.percent is None,
                }
            )

        groups = [
            {
                "ten_mang": key[2],
                "rows": sorted(
                    grouped[key],
                    key=lambda item: item["ma_chi_tieu"],
                ),
            }
            for key in sorted(grouped)
        ]
        department_blocks.append(
            {
                "phong_id": department.pk,
                "ma_phong": department.ma_phong,
                "ten_phong": department.ten_phong,
                "groups": groups,
            }
        )

    if include_pending:
        return department_blocks
    for block in department_blocks:
        for group in block["groups"]:
            for item in group["rows"]:
                item.pop("pending", None)
    return department_blocks


def _attribution_value(obj) -> date:
    return getattr(obj, "attribution_date", None)


def _phieu_source(phieu) -> tuple[str, str]:
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        return "Phiếu hoạt động", phieu.hoat_dong.ten
    if phieu.loai_phieu == LoaiPhieu.THANG and phieu.ky_id:
        return "Phiếu tháng", str(phieu.ky)
    if phieu.loai_phieu == LoaiPhieu.DU_AN and phieu.du_an_id:
        return "Phiếu dự án", phieu.du_an.ten_du_an
    return "Phiếu nhập liệu", str(phieu)


def build_drill_rows(indicator: ChiTieu, year: int) -> list[dict]:
    """Return the approved source rows that contributed to one indicator."""
    period = ReportPeriod.annual(year)
    year_start = date(year, 1, 1)
    department_id = indicator.nhom.phong_id
    contributions = []

    if indicator.cach_tong_hop == CachTongHop.COUNT:
        if (
            indicator.count_subject == CountSubject.ACTIVITY
            and indicator.loai_hoat_dong_id is not None
        ):
            queryset = _activity_count_queryset(
                year_start,
                period.end,
                OFFICIAL_STATUS,
                department_id,
            ).filter(
                hoat_dong__loai_hoat_dong_id=indicator.loai_hoat_dong_id
            )
            seen_activities = set()
            for phieu in queryset.select_related(
                "hoat_dong",
                "phong",
                "nguoi_nhap",
            ).order_by("attribution_date", "id"):
                if phieu.hoat_dong_id in seen_activities:
                    continue
                seen_activities.add(phieu.hoat_dong_id)
                contributions.append(
                    {
                        "loai": "Hoạt động",
                        "noi_dung": phieu.hoat_dong.ten,
                        "chi_tieu": indicator.ten_chi_tieu,
                        "ngay": _attribution_value(phieu),
                        "gia_tri": "",
                        "phieu": phieu,
                    }
                )
        elif (
            indicator.count_subject == CountSubject.PROJECT
            and indicator.loai_ho_tro
        ):
            queryset = _project_count_queryset(
                year_start,
                period.end,
                OFFICIAL_STATUS,
                department_id,
            ).filter(loai_ho_tro=indicator.loai_ho_tro)
            for support in queryset.select_related(
                "du_an",
                "phieu",
            ).order_by("ngay_ho_tro", "id"):
                contributions.append(
                    {
                        "loai": "Dòng hỗ trợ",
                        "noi_dung": support.du_an.ten_du_an,
                        "chi_tieu": support.noi_dung,
                        "ngay": support.ngay_ho_tro,
                        "gia_tri": format_vi_number(support.so_chuyen_gia),
                        "phieu": support.phieu,
                    }
                )
        return contributions

    indicator_ids = [indicator.pk]
    if indicator.cach_tong_hop == CachTongHop.RATIO:
        indicator_ids = [
            value
            for value in (
                indicator.chi_tieu_tu_so_id,
                indicator.chi_tieu_mau_so_id,
            )
            if value is not None
        ]

    queryset = (
        _solieu_queryset(
            year_start,
            period.end,
            OFFICIAL_STATUS,
            department_id,
        )
        .filter(
            chi_tieu_id__in=indicator_ids,
            doi_tuong__isnull=True,
            linh_vuc__isnull=True,
        )
        .select_related(
            "chi_tieu",
            "phieu",
            "phieu__hoat_dong",
            "phieu__ky",
            "phieu__du_an",
        )
        .order_by("attribution_date", "phieu_id", "id")
    )
    for value in queryset:
        kind, source = _phieu_source(value.phieu)
        contributions.append(
            {
                "loai": kind,
                "noi_dung": source,
                "chi_tieu": value.chi_tieu.ten_chi_tieu,
                "ngay": _attribution_value(value),
                "gia_tri": format_vi_number(value.gia_tri),
                "phieu": value.phieu,
            }
        )
    return contributions
