"""Post-login home summary and dashboard data endpoints."""

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import JsonResponse
from django.shortcuts import render
from django.urls import reverse
from django.utils.http import urlencode

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES, Role
from apps.accounts.scoping import scoped
from apps.catalog.models import ChiTieu
from apps.entry.models import PhieuNhapLieu, TrangThaiPhieu
from apps.reporting.dashboard import (
    chart_payload,
    cumulative_payload,
    department_completion,
    group_completion,
)
from apps.reporting.periods import today
from apps.reporting.report_data import allowed_departments
from apps.reporting.rollup import ReportPeriod, rollup

DASHBOARD_DEPARTMENT_CODE = "HTKN"


def _is_scoped(user) -> bool:
    return getattr(user, "role", None) in SCOPED_ROLES


def _requested_department(request, departments):
    """Return a department from ``?phong=`` after checking the menu scope."""
    raw = request.GET.get("phong")
    if raw in (None, ""):
        return None
    try:
        phong_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise PermissionDenied("Phòng ban không hợp lệ.") from exc
    for department in departments:
        if department.pk == phong_id:
            return department
    raise PermissionDenied("Bạn không có quyền xem phòng ban này.")


def _default_department(departments):
    for department in departments:
        if department.ma_phong == DASHBOARD_DEPARTMENT_CODE:
            return department
    return departments[0] if departments else None


def _my_phieu(user):
    queryset = scoped(
        user,
        PhieuNhapLieu.objects.filter(
            nguoi_nhap=user,
            trang_thai__in=(
                TrangThaiPhieu.NHAP,
                TrangThaiPhieu.TRA_LAI,
            ),
        ).select_related(
            "phong",
            "hoat_dong",
            "ky",
            "du_an",
            "nguoi_nhap",
        ),
        "phong_id",
    ).order_by("-id")
    drafts = []
    returned = []
    for phieu in queryset:
        if phieu.trang_thai == TrangThaiPhieu.NHAP:
            drafts.append(phieu)
        elif phieu.trang_thai == TrangThaiPhieu.TRA_LAI:
            returned.append(phieu)
    return drafts, returned


def _pending_count(user) -> int:
    return scoped(
        user,
        PhieuNhapLieu.objects.filter(
            phong_id=user.phong_id,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        ),
        "phong_id",
    ).count()


def _indicator_groups(rows):
    indicator_ids = {row.chi_tieu_id for row in rows}
    return {
        item["pk"]: item
        for item in ChiTieu.objects.filter(pk__in=indicator_ids).values(
            "pk",
            "nhom_id",
            "nhom__ten_mang",
            "nhom__thu_tu",
        )
    }


@login_required
def home(request):
    user = request.user
    if not can(user, "view_progress"):
        raise PermissionDenied

    departments = allowed_departments(user)
    scoped_user = _is_scoped(user)
    selected_department = (
        _requested_department(request, departments) if departments else None
    )
    if selected_department is None:
        selected_department = (
            departments[0] if scoped_user and departments else None
        )
    if selected_department is None and not scoped_user:
        selected_department = _default_department(departments)

    current_year = today().year

    # The switch on chart 2 requests only its data; the browser updates the
    # existing chart instead of initializing another one.
    if request.GET.get("chart") == "2":
        if selected_department is None:
            return JsonResponse(cumulative_payload([]))
        rows = rollup(
            ReportPeriod.annual(current_year),
            department_id=selected_department.pk,
        )
        return JsonResponse(cumulative_payload(rows))

    rows = rollup(
        ReportPeriod.annual(current_year),
        department_id=(
            selected_department.pk
            if scoped_user and selected_department
            else None
        ),
    )
    allowed_ids = {department.pk for department in departments}
    rows = [row for row in rows if row.phong_id in allowed_ids]

    completion_points = department_completion(rows, departments)
    if scoped_user:
        group_points = group_completion(rows, _indicator_groups(rows))
        chart1 = chart_payload(group_points, "ten_mang")
        chart1_title = "Bình quân % hoàn thành theo mảng chỉ tiêu"
    else:
        chart1 = chart_payload(completion_points, "ma_phong")
        chart1_title = "Bình quân % hoàn thành theo phòng ban"

    selected_rows = (
        [row for row in rows if row.phong_id == selected_department.pk]
        if selected_department
        else []
    )
    chart2 = cumulative_payload(selected_rows)

    drafts, returned = ([], [])
    pending_count = None
    if scoped_user:
        drafts, returned = _my_phieu(user)
    if getattr(user, "role", None) == Role.DEPARTMENT_HEAD:
        pending_count = _pending_count(user)

    progress_query = urlencode({"year": current_year})
    context = {
        "year": current_year,
        "is_scoped": scoped_user,
        "is_department_head": (
            getattr(user, "role", None) == Role.DEPARTMENT_HEAD
        ),
        "my_drafts": drafts,
        "my_returned": returned,
        "pending_count": pending_count,
        "completion_cards": completion_points,
        "departments": departments,
        "selected_department": selected_department,
        "show_department_switch": (
            not scoped_user and len(departments) > 1
        ),
        "chart1": chart1,
        "chart1_title": chart1_title,
        "chart2": chart2,
        "progress_url": f"{reverse('reporting:tien_do')}?{progress_query}",
    }
    return render(request, "home.html", context)
