"""Aggregation, Excel export, Word export, and published reports."""

from __future__ import annotations

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES
from apps.catalog.models import ChiTieu
from apps.reporting.docx_export import build_docx
from apps.reporting.exports import (
    content_stream,
    create_export_record,
    export_filename,
)
from apps.reporting.formatting import format_vi_number
from apps.reporting.forms import BaoCaoPeriodForm, XlsxUploadForm
from apps.reporting.periods import (
    KIND_MONTH,
    KIND_QUARTER,
    period_label,
    resolve_period,
    today,
)
from apps.reporting.progress import build_drill_rows, build_progress_groups
from apps.reporting.report_data import (
    allowed_departments,
    build_department_reports,
    collect_gaps,
    display_rows,
    gap_summary,
    load_notes,
    notes_from_post,
    resolve_scope,
    rollup_by_department,
    save_notes,
    scope_departments,
)
from apps.reporting.rollup import ReportPeriod, rollup
from apps.reporting.xlsx_export import build_workbook
from apps.reporting.xlsx_import import WorkbookFormatError, parse_workbook

SCOPE_PARAMS = ("kind", "year", "month", "quarter", "phong")


def _require_view(user):
    if not (
        can(user, "view_progress")
        or can(user, "export_department_report")
        or can(user, "export_center_report")
    ):
        raise PermissionDenied


def _is_scoped(user) -> bool:
    return getattr(user, "role", None) in SCOPED_ROLES


def _guard_requested_phong(request, departments) -> None:
    """Reject a cross-department scope before the form can silently drop it."""
    raw = request.POST.get("phong")
    if raw is None:
        raw = request.GET.get("phong")
    if raw in (None, ""):
        return
    try:
        phong_id = int(raw)
    except (TypeError, ValueError) as exc:
        raise PermissionDenied("Phạm vi phòng ban không hợp lệ.") from exc
    if phong_id not in {phong.pk for phong in departments}:
        raise PermissionDenied("Bạn không có quyền xem báo cáo phòng này.")


def _has_scope_params(request) -> bool:
    return any(name in request.GET for name in SCOPE_PARAMS)


def _default_period():
    current = today()
    return resolve_period(
        KIND_MONTH,
        current.year,
        month=current.month,
    )


def _query_params(period, scope, accepted: bool) -> list[tuple[str, str]]:
    params = [
        ("kind", period.kind),
        ("year", str(period.year)),
    ]
    if period.kind == KIND_MONTH:
        params.append(("month", str(period.start.month)))
    elif period.kind == KIND_QUARTER:
        params.append(("quarter", str((period.start.month - 1) // 3 + 1)))
    if scope.phong is not None:
        params.append(("phong", str(scope.phong.pk)))
    if accepted:
        params.append(("tiep_tuc", "1"))
    return params


def _preview_url(period, scope, accepted: bool) -> str:
    return (
        f"{reverse('reporting:bao_cao')}?"
        f"{urlencode(_query_params(period, scope, accepted))}"
    )


def _scope_fields(period, scope) -> dict:
    fields = {
        "kind": period.kind,
        "year": period.year,
    }
    if period.kind == KIND_MONTH:
        fields["month"] = period.start.month
    elif period.kind == KIND_QUARTER:
        fields["quarter"] = (period.start.month - 1) // 3 + 1
    if scope.phong is not None:
        fields["phong"] = scope.phong.pk
    return fields


def _accepted(request) -> bool:
    value = request.POST.get("tiep_tuc", request.GET.get("tiep_tuc", ""))
    return value in ("1", "true", "on", "yes")


def _notes_for_request(
    request,
    period,
    departments,
    rows_by_department,
) -> dict[tuple[int, int], str]:
    notes = load_notes(request, period, departments, rows_by_department)
    posted_notes = notes_from_post(request, departments, rows_by_department)
    if posted_notes:
        notes.update(posted_notes)
        save_notes(
            request,
            period,
            departments,
            rows_by_department,
            notes,
        )
    return notes


def _load_report_data(request, period, scope, user, accepted: bool):
    departments = scope_departments(scope, user)
    rows_by_department = rollup_by_department(period, departments)
    gaps_by_department = collect_gaps(period, departments)
    notes = _notes_for_request(
        request,
        period,
        departments,
        rows_by_department,
    )
    reports, gaps_by_department = build_department_reports(
        period=period,
        departments=departments,
        notes=notes,
        accepted=accepted,
        rows_by_department=rows_by_department,
        gaps_by_department=gaps_by_department,
    )
    return departments, reports, gaps_by_department


def _render_report(
    request,
    *,
    form,
    period,
    scope,
    user,
    accepted: bool,
):
    departments, reports, gaps_by_department = _load_report_data(
        request,
        period,
        scope,
        user,
        accepted,
    )
    has_gaps = any(report.gaps for report in reports)
    report_blocks = [
        {
            "report": report,
            "rows": display_rows(report, accepted=accepted),
            "co_danh_gia": report.co_danh_gia,
        }
        for report in reports
    ]
    context = {
        "form": form,
        "is_scoped": _is_scoped(user),
        "period": period,
        "period_label": period_label(period),
        "scope": scope,
        "departments": departments,
        "reports": report_blocks,
        "gaps_by_department": gaps_by_department,
        "has_gaps": has_gaps,
        "accepted": accepted,
        "gap_summary": gap_summary(reports, accepted),
        "continue_url": _preview_url(period, scope, True),
        "save_url": _preview_url(period, scope, accepted),
        "export_xlsx_url": reverse(
            "reporting:xuat_bao_cao",
            args=["xlsx"],
        ),
        "export_docx_url": reverse(
            "reporting:xuat_bao_cao",
            args=["docx"],
        ),
        "hidden_scope": _scope_fields(period, scope),
        "tiep_tuc_value": "1" if accepted else "",
    }
    return render(request, "reporting/bao_cao.html", context)


@login_required
@require_http_methods(["GET", "POST"])
def bao_cao(request):
    _require_view(request.user)
    departments = allowed_departments(request.user)
    _guard_requested_phong(request, departments)

    if request.method == "POST":
        form = BaoCaoPeriodForm(request.POST, departments=departments)
        if form.is_valid():
            period = form.period
            scope = resolve_scope(request.user, form.cleaned_data.get("phong"))
            accepted = _accepted(request)
            _load_report_data(
                request,
                period,
                scope,
                request.user,
                accepted,
            )
            messages.success(request, "Đã lưu đánh giá hiệu quả.")
            return redirect(_preview_url(period, scope, accepted))
    else:
        if _has_scope_params(request):
            form = BaoCaoPeriodForm(request.GET, departments=departments)
        else:
            form = BaoCaoPeriodForm(departments=departments)
            if _is_scoped(request.user):
                form.fields["phong"].initial = request.user.phong_id

    if not form.is_bound or form.is_valid():
        if form.is_bound:
            period = form.period
            scope = resolve_scope(
                request.user,
                form.cleaned_data.get("phong"),
            )
        else:
            period = _default_period()
            initial_phong = (
                request.user.phong if _is_scoped(request.user) else None
            )
            scope = resolve_scope(request.user, initial_phong)
        return _render_report(
            request,
            form=form,
            period=period,
            scope=scope,
            user=request.user,
            accepted=_accepted(request),
        )

    return render(
        request,
        "reporting/bao_cao.html",
        {
            "form": form,
            "is_scoped": _is_scoped(request.user),
            "reports": [],
            "period_label": "",
            "has_gaps": False,
            "accepted": False,
        },
    )


@login_required
@require_POST
def xuat_bao_cao(request, dinh_dang):
    if dinh_dang not in ("xlsx", "docx"):
        raise Http404("Định dạng báo cáo không hợp lệ.")
    _require_view(request.user)
    departments = allowed_departments(request.user)
    _guard_requested_phong(request, departments)
    form = BaoCaoPeriodForm(request.POST, departments=departments)
    if not form.is_valid():
        return render(
            request,
            "reporting/bao_cao.html",
            {
                "form": form,
                "is_scoped": _is_scoped(request.user),
                "reports": [],
                "period_label": "",
                "has_gaps": False,
                "accepted": False,
            },
        )

    period = form.period
    scope = resolve_scope(request.user, form.cleaned_data.get("phong"))
    accepted = _accepted(request)
    departments = scope_departments(scope, request.user)
    rows_by_department = rollup_by_department(period, departments)
    gaps_by_department = collect_gaps(period, departments)
    notes = _notes_for_request(
        request,
        period,
        departments,
        rows_by_department,
    )
    reports, _gaps = build_department_reports(
        period=period,
        departments=departments,
        notes=notes,
        accepted=accepted,
        rows_by_department=rows_by_department,
        gaps_by_department=gaps_by_department,
    )
    if any(report.gaps for report in reports) and not accepted:
        messages.warning(
            request,
            "Còn số liệu chưa đầy đủ. Chọn “Vẫn lập báo cáo” trước khi xuất.",
        )
        return redirect(_preview_url(period, scope, False))

    ky = period_label(period)
    if dinh_dang == "xlsx":
        content = build_workbook(
            reports,
            period_label=ky,
            accepted=accepted,
        )
    else:
        content = build_docx(
            reports,
            period_label=ky,
            accepted=accepted,
            user_label=request.user.ho_ten or request.user.username,
            is_center=scope.is_center,
        )

    filename = export_filename(period, scope.phong, dinh_dang)
    create_export_record(
        period_label=ky,
        phong=scope.phong,
        user=request.user,
        dinh_dang=dinh_dang,
        filename=filename,
        content=content,
        reports=reports,
        accepted=accepted,
    )
    return FileResponse(
        content_stream(content),
        as_attachment=True,
        filename=filename,
    )


@login_required
@require_http_methods(["GET", "POST"])
def nhap_xlsx(request):
    _require_view(request.user)
    form = XlsxUploadForm(request.POST or None, request.FILES or None)
    preview_rows = []
    column_count = 0
    parsed_name = ""
    if request.method == "POST" and form.is_valid():
        uploaded = form.cleaned_data["file"]
        try:
            preview_rows, column_count = parse_workbook(uploaded)
        except WorkbookFormatError as exc:
            form.add_error("file", str(exc))
        else:
            parsed_name = uploaded.name
    return render(
        request,
        "reporting/xlsx_import.html",
        {
            "form": form,
            "preview_rows": preview_rows,
            "column_count": column_count,
            "parsed_name": parsed_name,
        },
    )


def _progress_year(request) -> tuple[int, str]:
    raw = (request.GET.get("year") or "").strip()
    if not raw:
        return today().year, ""
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return today().year, "Năm không hợp lệ. Đang hiển thị năm hiện tại."
    if not 2000 <= year <= 2100:
        return today().year, "Năm phải từ 2000 đến 2100."
    return year, ""


def _progress_department(request, departments):
    """Resolve the progress filter without ever leaking another department."""
    raw = (request.GET.get("phong") or "").strip()
    if raw:
        try:
            phong_id = int(raw)
        except (TypeError, ValueError) as exc:
            raise PermissionDenied("Phòng ban không hợp lệ.") from exc
        for department in departments:
            if department.pk == phong_id:
                return department
        raise PermissionDenied("Bạn không có quyền xem phòng ban này.")
    if _is_scoped(request.user):
        return departments[0] if departments else None
    return None


def _toggle_pending(request) -> bool:
    return request.GET.get("gom_cho_duyet", "").lower() in (
        "1",
        "true",
        "on",
        "yes",
    )


@login_required
@require_http_methods(["GET"])
def tien_do(request):
    if not can(request.user, "view_progress"):
        raise PermissionDenied

    departments = allowed_departments(request.user)
    selected_department = _progress_department(request, departments)
    year, year_error = _progress_year(request)
    include_pending = _toggle_pending(request)

    rows = rollup(
        ReportPeriod.annual(year),
        department_id=(
            selected_department.pk if selected_department else None
        ),
        include_pending=include_pending,
    )
    allowed_ids = {department.pk for department in departments}
    rows = [row for row in rows if row.phong_id in allowed_ids]
    visible_departments = (
        [selected_department] if selected_department else departments
    )
    department_blocks = build_progress_groups(
        rows,
        visible_departments,
        include_pending=include_pending,
    )
    return render(
        request,
        "reporting/tien_do.html",
        {
            "year": year,
            "year_error": year_error,
            "departments": departments,
            "selected_department": selected_department,
            "show_department_filter": not _is_scoped(request.user),
            "include_pending": include_pending,
            "department_blocks": department_blocks,
        },
    )


@login_required
@require_http_methods(["GET"])
def tien_do_chi_tiet(request, chi_tieu_id):
    if not can(request.user, "view_progress"):
        raise PermissionDenied

    year, year_error = _progress_year(request)
    indicator = get_object_or_404(
        ChiTieu.objects.select_related("nhom__phong"),
        pk=chi_tieu_id,
    )
    allowed_ids = {
        department.pk
        for department in allowed_departments(request.user)
    }
    if indicator.nhom.phong_id not in allowed_ids:
        raise PermissionDenied("Bạn không có quyền xem chỉ tiêu này.")

    rows = rollup(
        ReportPeriod.annual(year),
        department_id=indicator.nhom.phong_id,
    )
    summary = next(
        (row for row in rows if row.chi_tieu_id == indicator.pk),
        None,
    )
    summary_view = None
    if summary is not None:
        summary_view = {
            "plan": format_vi_number(summary.plan),
            "cumulative": format_vi_number(summary.cumulative),
            "percent": format_vi_number(summary.percent),
            "remainder": format_vi_number(summary.remainder),
        }
    return render(
        request,
        "reporting/tien_do_chi_tiet.html",
        {
            "year": year,
            "year_error": year_error,
            "indicator": indicator,
            "summary": summary_view,
            "contributions": build_drill_rows(indicator, year),
        },
    )
