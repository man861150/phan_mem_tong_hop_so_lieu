"""Scope, missing-data, and presentation helpers for periodic reports.

All figures come from :func:`apps.reporting.rollup.rollup`. This module only
adds labels, warnings, and the department-specific lists around those rows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date

from django.core.exceptions import PermissionDenied
from django.db.models import Q

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES
from apps.accounts.scoping import scoped
from apps.activities.models import HoatDong, TrangThaiHoatDong
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    CountSubject,
    KieuGhiNhan,
    PhongBan,
)
from apps.entry.models import LoaiPhieu, PhieuNhapLieu, SoLieu, TrangThaiPhieu
from apps.reporting.formatting import format_vi_number
from apps.reporting.periods import months_in_period, period_slug, today
from apps.reporting.rollup import ReportPeriod, RollupRow, rollup

REPORT_DEPARTMENT_CODES = ("GDCN", "TTTK", "HTKN")
CENTER_LABEL = "Toàn trung tâm"
GAP_NOTE = "Số liệu chưa đầy đủ"
SESSION_NOTE_KEY = "reporting_danh_gia"

GAP_MONTH = "thieu_phieu_thang"
GAP_ACTIVITY = "thieu_phieu_hoat_dong"
GAP_PENDING = "phieu_cho_duyet"


@dataclass(frozen=True)
class ReportScope:
    phong: PhongBan | None
    is_center: bool

    @property
    def label(self) -> str:
        if self.is_center or self.phong is None:
            return CENTER_LABEL
        return f"{self.phong.ma_phong} — {self.phong.ten_phong}"


@dataclass(frozen=True)
class MissingInput:
    phong: PhongBan
    loai: str
    mo_ta: str
    chi_tieu_ids: frozenset[int] = field(default_factory=frozenset)


@dataclass
class DepartmentReport:
    phong: PhongBan
    rows: list[RollupRow]
    gaps: list[MissingInput] = field(default_factory=list)
    affected_ids: set[int] = field(default_factory=set)
    notes: dict[int, str] = field(default_factory=dict)
    activities: list[dict] = field(default_factory=list)
    projects: list[dict] = field(default_factory=list)
    breakdowns: list[dict] = field(default_factory=list)

    @property
    def ma_phong(self):
        return self.phong.ma_phong

    @property
    def ten(self):
        return self.phong.ten_phong

    @property
    def co_danh_gia(self):
        return self.phong.ma_phong == "TTTK"


def allowed_departments(user) -> list[PhongBan]:
    """Return the reporting departments the user may read, center-stacked."""
    base = scoped(
        user,
        PhongBan.objects.filter(dang_su_dung=True),
        "id",
    )
    departments = list(base.filter(ma_phong__in=REPORT_DEPARTMENT_CODES))
    departments.sort(
        key=lambda phong: REPORT_DEPARTMENT_CODES.index(phong.ma_phong)
        if phong.ma_phong in REPORT_DEPARTMENT_CODES
        else len(REPORT_DEPARTMENT_CODES)
    )
    if not departments and getattr(user, "role", None) in SCOPED_ROLES:
        if user.phong_id and can(
            user, "export_department_report", user.phong_id
        ):
            return [user.phong]
    return departments


def resolve_scope(user, requested_phong: PhongBan | None) -> ReportScope:
    """Resolve a requested department without ever leaking another one.

    Scoped roles are fixed to their own department. A cross-department request
    raises ``PermissionDenied`` instead of silently returning another scope.
    """
    if getattr(user, "role", None) in SCOPED_ROLES:
        if not user.phong_id:
            raise PermissionDenied("Tài khoản chưa được gán phòng ban.")
        if requested_phong is not None and requested_phong.pk != user.phong_id:
            raise PermissionDenied("Bạn không có quyền xem báo cáo phòng khác.")
        if not can(user, "export_department_report", user.phong_id):
            raise PermissionDenied("Bạn không có quyền xuất báo cáo phòng.")
        return ReportScope(phong=user.phong, is_center=False)

    if requested_phong is not None:
        if requested_phong not in allowed_departments(user):
            raise PermissionDenied("Bạn không có quyền xem báo cáo phòng này.")
        if not can(
            user, "export_department_report", requested_phong.pk
        ):
            raise PermissionDenied("Bạn không có quyền xuất báo cáo phòng.")
        return ReportScope(phong=requested_phong, is_center=False)

    if not can(user, "export_center_report"):
        raise PermissionDenied("Bạn không có quyền xuất báo cáo toàn trung tâm.")
    return ReportScope(phong=None, is_center=True)


def scope_departments(scope: ReportScope, user) -> list[PhongBan]:
    if scope.is_center:
        return allowed_departments(user)
    return [scope.phong] if scope.phong is not None else []


def rollup_by_department(
    period: ReportPeriod,
    departments: list[PhongBan],
) -> dict[int, list[RollupRow]]:
    return {
        phong.pk: rollup(period, department_id=phong.pk)
        for phong in departments
    }


def _activity_anchor(activity: HoatDong) -> date:
    return activity.den_ngay or activity.tu_ngay


def _period_contains(period: ReportPeriod, value: date | None) -> bool:
    return value is not None and period.start <= value <= period.end


def _monthly_indicator_ids(phong: PhongBan) -> frozenset[int]:
    return frozenset(
        ChiTieu.objects.filter(
            nhom__phong=phong,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
        ).values_list("pk", flat=True)
    )


def _activity_indicator_ids(
    phong: PhongBan,
    loai_hoat_dong_id: int,
) -> frozenset[int]:
    return frozenset(
        ChiTieu.objects.filter(nhom__phong=phong)
        .filter(
            Q(loai_hoat_dong_id=loai_hoat_dong_id)
            | Q(bieu_mau__loai_hoat_dong_id=loai_hoat_dong_id)
        )
        .distinct()
        .values_list("pk", flat=True)
    )


def _project_indicator_ids(phong: PhongBan) -> frozenset[int]:
    return frozenset(
        ChiTieu.objects.filter(
            nhom__phong=phong,
        )
        .filter(
            Q(kieu_ghi_nhan=KieuGhiNhan.PROJECT)
            | Q(
                cach_tong_hop=CachTongHop.COUNT,
                count_subject=CountSubject.PROJECT,
            )
        )
        .values_list("pk", flat=True)
    )


def _period_monthly_gaps(
    period: ReportPeriod,
    phong: PhongBan,
) -> list[MissingInput]:
    monthly_ids = _monthly_indicator_ids(phong)
    gaps = []
    cutoff = today()
    for year, month in months_in_period(period):
        if date(year, month, 1) > cutoff:
            continue
        exists = PhieuNhapLieu.objects.filter(
            loai_phieu=LoaiPhieu.THANG,
            phong=phong,
            ky__nam=year,
            ky__so_ky=month,
        ).exists()
        if not exists:
            gaps.append(
                MissingInput(
                    phong=phong,
                    loai=GAP_MONTH,
                    mo_ta=f"Tháng {month}/{year} chưa có phiếu tháng.",
                    chi_tieu_ids=monthly_ids,
                )
            )
    return gaps


def _activities_in_period(
    period: ReportPeriod,
    phong: PhongBan,
):
    activities = HoatDong.objects.filter(
        loai_hoat_dong__phong=phong,
    ).select_related("loai_hoat_dong", "loai_hoat_dong__phong")
    return [
        activity
        for activity in activities
        if _period_contains(period, _activity_anchor(activity))
    ]


def _activity_phieu_map(activities) -> dict[int, str]:
    """Load one phiếu status per activity in one query."""
    activity_ids = [activity.pk for activity in activities]
    if not activity_ids:
        return {}
    rows = PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.HOAT_DONG,
        hoat_dong_id__in=activity_ids,
    ).values_list("hoat_dong_id", "trang_thai")
    mapping = {}
    for activity_id, status in rows:
        mapping.setdefault(activity_id, status)
    return mapping


def _activity_indicator_map(phong, loai_ids) -> dict[int, frozenset[int]]:
    """Load indicator ids for every activity type in one query."""
    loai_ids = list(dict.fromkeys(loai_ids))
    if not loai_ids:
        return {}
    rows = (
        ChiTieu.objects.filter(nhom__phong=phong)
        .filter(
            Q(loai_hoat_dong_id__in=loai_ids)
            | Q(bieu_mau__loai_hoat_dong_id__in=loai_ids)
        )
        .values_list(
            "pk",
            "loai_hoat_dong_id",
            "bieu_mau__loai_hoat_dong_id",
        )
    )
    grouped = {}
    for pk, direct_id, form_id in rows:
        if direct_id in loai_ids:
            grouped.setdefault(direct_id, set()).add(pk)
        if form_id in loai_ids:
            grouped.setdefault(form_id, set()).add(pk)
    return {
        loai_id: frozenset(indicator_ids)
        for loai_id, indicator_ids in grouped.items()
    }


def _activity_gaps(
    period: ReportPeriod,
    phong: PhongBan,
) -> list[MissingInput]:
    activities = [
        activity
        for activity in _activities_in_period(period, phong)
        if activity.trang_thai == TrangThaiHoatDong.DA_TO_CHUC
    ]
    phieu_map = _activity_phieu_map(activities)
    missing = [
        activity for activity in activities if activity.pk not in phieu_map
    ]
    if not missing:
        return []
    indicator_map = _activity_indicator_map(
        phong,
        [activity.loai_hoat_dong_id for activity in missing],
    )
    gaps = []
    for activity in missing:
        gaps.append(
            MissingInput(
                phong=phong,
                loai=GAP_ACTIVITY,
                mo_ta=(
                    f"Hoạt động “{activity.ten}” đã tổ chức nhưng chưa có "
                    "phiếu kết quả."
                ),
                chi_tieu_ids=indicator_map.get(
                    activity.loai_hoat_dong_id,
                    frozenset(),
                ),
            )
        )
    return gaps


def _phieu_in_period(period: ReportPeriod, phieu: PhieuNhapLieu) -> bool:
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        return _period_contains(period, _activity_anchor(phieu.hoat_dong))
    if phieu.loai_phieu == LoaiPhieu.THANG and phieu.ky_id:
        ky = phieu.ky
        anchor = ky.tu_ngay or date(ky.nam, ky.so_ky, 1)
        return _period_contains(period, anchor)
    if phieu.loai_phieu == LoaiPhieu.DU_AN and phieu.du_an_id:
        return any(
            _period_contains(period, line.ngay_ho_tro)
            for line in phieu.ho_tro_du_an.all()
        )
    return False


def _pending_gaps(
    period: ReportPeriod,
    phong: PhongBan,
) -> list[MissingInput]:
    phieus = (
        PhieuNhapLieu.objects.filter(
            phong=phong,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )
        .select_related("hoat_dong", "ky", "du_an")
        .prefetch_related("ho_tro_du_an")
    )
    gaps = []
    for phieu in phieus:
        if not _phieu_in_period(period, phieu):
            continue
        ids = frozenset(
            SoLieu.objects.filter(phieu=phieu).values_list(
                "chi_tieu_id", flat=True
            )
        )
        if not ids:
            if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
                ids = _activity_indicator_ids(
                    phong,
                    phieu.hoat_dong.loai_hoat_dong_id,
                )
            elif phieu.loai_phieu == LoaiPhieu.THANG:
                ids = _monthly_indicator_ids(phong)
            elif phieu.loai_phieu == LoaiPhieu.DU_AN:
                ids = _project_indicator_ids(phong)
        gaps.append(
            MissingInput(
                phong=phong,
                loai=GAP_PENDING,
                mo_ta=f"Phiếu “{phieu}” đang chờ duyệt.",
                chi_tieu_ids=ids,
            )
        )
    return gaps


def collect_gaps(
    period: ReportPeriod,
    departments: list[PhongBan],
) -> dict[int, list[MissingInput]]:
    return {
        phong.pk: [
            *_period_monthly_gaps(period, phong),
            *_activity_gaps(period, phong),
            *_pending_gaps(period, phong),
        ]
        for phong in departments
    }


def affected_indicator_ids(
    gaps_by_department: dict[int, list[MissingInput]],
    rows_by_department: dict[int, list[RollupRow]],
) -> dict[int, set[int]]:
    """Map gaps to the indicators they can make incomplete.

    When a gap cannot be linked to a specific indicator, every row in that
    department is marked so the warning is never hidden.
    """
    affected = {}
    for phong_id, gaps in gaps_by_department.items():
        ids = set()
        for gap in gaps:
            if gap.chi_tieu_ids:
                ids.update(gap.chi_tieu_ids)
        row_ids = {row.chi_tieu_id for row in rows_by_department.get(phong_id, [])}
        if gaps and not (ids & row_ids):
            ids.update(row_ids)
        affected[phong_id] = ids & row_ids if row_ids else ids
    return affected


def _note_key(
    period: ReportPeriod,
    phong_id: int,
    chi_tieu_id: int,
) -> str:
    return f"{period_slug(period)}:{phong_id}:{chi_tieu_id}"


def load_notes(
    request,
    period: ReportPeriod,
    departments: list[PhongBan],
    rows_by_department: dict[int, list[RollupRow]],
) -> dict[tuple[int, int], str]:
    stored = request.session.get(SESSION_NOTE_KEY, {})
    notes = {}
    for phong in departments:
        for row in rows_by_department.get(phong.pk, []):
            value = stored.get(_note_key(period, phong.pk, row.chi_tieu_id), "")
            if value:
                notes[(phong.pk, row.chi_tieu_id)] = value
    return notes


def save_notes(
    request,
    period: ReportPeriod,
    departments: list[PhongBan],
    rows_by_department: dict[int, list[RollupRow]],
    notes: dict[tuple[int, int], str],
) -> None:
    stored = dict(request.session.get(SESSION_NOTE_KEY, {}))
    for phong in departments:
        if not can(request.user, "export_department_report", phong.pk):
            continue
        for row in rows_by_department.get(phong.pk, []):
            key = _note_key(period, phong.pk, row.chi_tieu_id)
            value = (notes.get((phong.pk, row.chi_tieu_id)) or "").strip()
            if value:
                stored[key] = value
            else:
                stored.pop(key, None)
    request.session[SESSION_NOTE_KEY] = stored


def notes_from_post(
    request,
    departments: list[PhongBan],
    rows_by_department: dict[int, list[RollupRow]],
) -> dict[tuple[int, int], str]:
    """Read note fields from an export or save form.

    Only fields present in the form are changed; an export without note fields
    keeps the session values loaded by :func:`load_notes`.
    """
    notes = {}
    for phong in departments:
        for row in rows_by_department.get(phong.pk, []):
            key = f"danh_gia_{phong.pk}_{row.chi_tieu_id}"
            if key in request.POST:
                notes[(phong.pk, row.chi_tieu_id)] = request.POST.get(
                    key, ""
                ).strip()
    return notes


def _format_date(value: date | None) -> str:
    return value.strftime("%d/%m/%Y") if value else "—"


def activities_for_department(
    period: ReportPeriod,
    phong: PhongBan,
) -> list[dict]:
    activity_rows = _activities_in_period(period, phong)
    phieu_map = _activity_phieu_map(activity_rows)
    activities = []
    for activity in activity_rows:
        ad_hoc = activity.la_nhiem_vu_phat_sinh
        activities.append(
            {
                "id": activity.pk,
                "ten": activity.ten,
                "loai": activity.loai_hoat_dong.ten_loai,
                "thoi_gian": (
                    f"{_format_date(activity.tu_ngay)} – "
                    f"{_format_date(activity.den_ngay or activity.tu_ngay)}"
                ),
                "trang_thai": activity.get_trang_thai_display(),
                "noi_dung": (activity.noi_dung or "") if ad_hoc else "",
                "ket_qua": (activity.ket_qua or "") if ad_hoc else "",
                "phieu": activity.pk in phieu_map,
            }
        )
    activities.sort(key=lambda item: (item["loai"], item["thoi_gian"], item["id"]))
    return activities


def projects_for_department(
    period: ReportPeriod,
    phong: PhongBan,
) -> list[dict]:
    from apps.entry.models import HoTroDuAn

    lines = (
        HoTroDuAn.objects.filter(
            du_an__phong=phong,
            ngay_ho_tro__gte=period.start,
            ngay_ho_tro__lte=period.end,
        )
        .select_related("du_an", "phieu")
        .order_by("ngay_ho_tro", "id")
    )
    return [
        {
            "du_an": line.du_an.ten_du_an,
            "noi_dung": line.noi_dung,
            "loai_ho_tro": line.get_loai_ho_tro_display(),
            "ngay": _format_date(line.ngay_ho_tro),
            "trang_thai": line.phieu.get_trang_thai_display(),
        }
        for line in lines
    ]


def breakdown_rows(rows: list[RollupRow]) -> list[dict]:
    result = []
    for row in rows:
        dimensions = []
        if row.doi_tuong:
            dimensions.append(
                {
                    "ten": "Đối tượng",
                    "items": [
                        {
                            "ten": item.ten,
                            "value": format_vi_number(item.value),
                            "raw": item.value,
                        }
                        for item in row.doi_tuong
                    ],
                }
            )
        for key, label in (
            ("qd36", "Lĩnh vực QĐ 36"),
            ("tt24", "Lĩnh vực TT 24"),
        ):
            items = row.linh_vuc.get(key, [])
            if items:
                dimensions.append(
                    {
                        "ten": label,
                        "items": [
                            {
                                "ten": f"{item.ma} — {item.ten}",
                                "value": format_vi_number(item.value),
                                "raw": item.value,
                            }
                            for item in items
                        ],
                    }
                )
        if row.nguon:
            dimensions.append(
                {
                    "ten": "Nguồn số liệu",
                    "items": [
                        {
                            "ten": item.ten,
                            "value": format_vi_number(item.value),
                            "raw": item.value,
                        }
                        for item in row.nguon
                    ],
                }
            )
        if dimensions:
            result.append(
                {
                    "chi_tieu": row.ten_chi_tieu,
                    "ma_chi_tieu": row.ma_chi_tieu,
                    "dimensions": dimensions,
                }
            )
    return result


def breakdown_label(row: RollupRow) -> str:
    """Freeze the available breakdown dimensions on one snapshot line."""
    parts = []
    if row.doi_tuong:
        parts.append(
            "Đối tượng: "
            + ", ".join(
                f"{item.ten}={format_vi_number(item.value)}"
                for item in row.doi_tuong
            )
        )
    for key, label in (
        ("qd36", "Lĩnh vực QĐ 36"),
        ("tt24", "Lĩnh vực TT 24"),
    ):
        items = row.linh_vuc.get(key, [])
        if items:
            parts.append(
                f"{label}: "
                + ", ".join(
                    f"{item.ma}={format_vi_number(item.value)}"
                    for item in items
                )
            )
    if row.nguon:
        parts.append(
            "Nguồn: "
            + ", ".join(
                f"{item.ten}={format_vi_number(item.value)}"
                for item in row.nguon
            )
        )
    return " | ".join(parts)


def display_rows(
    report: DepartmentReport,
    *,
    accepted: bool,
) -> list[dict]:
    rows = []
    for row in report.rows:
        note = GAP_NOTE if accepted and row.chi_tieu_id in report.affected_ids else ""
        rows.append(
            {
                "chi_tieu_id": row.chi_tieu_id,
                "chi_tieu": row.ten_chi_tieu,
                "don_vi_tinh": row.don_vi_tinh,
                "ke_hoach": format_vi_number(row.plan),
                "thuc_hien": format_vi_number(row.period_value),
                "luy_ke": format_vi_number(row.cumulative),
                "phan_tram": format_vi_number(row.percent),
                "ghi_chu": note,
                "danh_gia": report.notes.get(row.chi_tieu_id, ""),
                "behind": row.behind,
            }
        )
    return rows


def build_department_reports(
    *,
    period: ReportPeriod,
    departments: list[PhongBan],
    notes: dict[tuple[int, int], str],
    accepted: bool,
    rows_by_department: dict[int, list[RollupRow]] | None = None,
    gaps_by_department: dict[int, list[MissingInput]] | None = None,
) -> tuple[list[DepartmentReport], dict[int, list[MissingInput]]]:
    if rows_by_department is None:
        rows_by_department = rollup_by_department(period, departments)
    if gaps_by_department is None:
        gaps_by_department = collect_gaps(period, departments)
    affected = affected_indicator_ids(gaps_by_department, rows_by_department)
    reports = []
    for phong in departments:
        dept_notes = {
            chi_tieu_id: value
            for (phong_id, chi_tieu_id), value in notes.items()
            if phong_id == phong.pk
        }
        reports.append(
            DepartmentReport(
                phong=phong,
                rows=rows_by_department.get(phong.pk, []),
                gaps=gaps_by_department.get(phong.pk, []),
                affected_ids=affected.get(phong.pk, set()),
                notes=dept_notes,
                activities=activities_for_department(period, phong),
                projects=projects_for_department(period, phong),
                breakdowns=breakdown_rows(rows_by_department.get(phong.pk, [])),
            )
        )
    return reports, gaps_by_department


def gap_summary(
    reports: list[DepartmentReport],
    accepted: bool,
) -> str:
    if not accepted:
        return ""
    lines = []
    for report in reports:
        for gap in report.gaps:
            lines.append(gap.mo_ta)
    if not lines:
        return ""
    return "Số liệu chưa đầy đủ: " + "; ".join(lines)
