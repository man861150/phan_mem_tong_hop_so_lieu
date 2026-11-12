"""Aggregation, Excel export, Word export, and published reports."""

from __future__ import annotations

from decimal import Decimal
from pathlib import Path

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.core.paginator import Paginator
from django.db.models import Q
from django.http import FileResponse, Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.utils.http import urlencode
from django.views.decorators.http import require_http_methods, require_POST

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES
from apps.accounts.scoping import scoped
from apps.activities.models import HoatDong
from apps.catalog.models import (
    ChiTieu,
    DanhMucLinhVuc,
    LoaiHoatDong,
    PhongBan,
)
from apps.entry.models import LoaiPhieu, PhieuNhapLieu
from apps.reporting.docx_export import build_docx
from apps.reporting.exports import (
    content_stream,
    create_export_record,
    export_filename,
)
from apps.reporting.formatting import format_vi_number
from apps.reporting.forms import BaoCaoPeriodForm, XlsxUploadForm
from apps.reporting.models import BaoCaoDaXuat
from apps.reporting.periods import (
    KIND_MONTH,
    KIND_QUARTER,
    months_in_period,
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


PUBLISHED_CONTENT_TYPES = {
    "xlsx": (
        "application/vnd.openxmlformats-officedocument."
        "spreadsheetml.sheet"
    ),
    "docx": (
        "application/vnd.openxmlformats-officedocument."
        "wordprocessingml.document"
    ),
}
PUBLISHED_PAGE_SIZE = 50


def _published_queryset(user):
    return scoped(
        user,
        BaoCaoDaXuat.objects.select_related("phong", "nguoi_lap"),
        "phong_id",
    )


@login_required
@require_http_methods(["GET"])
def da_xuat(request):
    """List immutable reports visible inside the caller's scope."""
    _require_view(request.user)
    page_obj = Paginator(
        _published_queryset(request.user).order_by("-ngay_lap", "-id"),
        PUBLISHED_PAGE_SIZE,
    ).get_page(request.GET.get("trang"))
    return render(
        request,
        "reporting/da_xuat.html",
        {
            "page_obj": page_obj,
            "reports": page_obj.object_list,
        },
    )


@login_required
@require_http_methods(["GET"])
def tai_bao_cao(request, bao_cao_id):
    """Return the stored file; never regenerate a published report."""
    _require_view(request.user)
    record = get_object_or_404(
        _published_queryset(request.user),
        pk=bao_cao_id,
    )
    if not record.file.storage.exists(record.file.name):
        raise Http404("Tệp báo cáo không còn tồn tại.")
    content_type = PUBLISHED_CONTENT_TYPES.get(record.dinh_dang)
    if content_type is None:
        raise Http404("Định dạng báo cáo không hợp lệ.")
    return FileResponse(
        record.file.open("rb"),
        as_attachment=True,
        filename=Path(record.file.name).name,
        content_type=content_type,
    )


SEARCH_PAGE_SIZE = 25
SEARCH_PERIOD_CHOICES = (
    [("", "Cả năm")]
    + [(f"thang-{month}", f"Tháng {month}") for month in range(1, 13)]
    + [(f"quy-{quarter}", f"Quý {quarter}") for quarter in range(1, 5)]
)


def _search_year(raw):
    if not raw:
        return today().year, ""
    try:
        year = int(raw)
    except (TypeError, ValueError):
        return today().year, "Năm không hợp lệ."
    if not 2000 <= year <= 2100:
        return today().year, "Năm phải từ 2000 đến 2100."
    return year, ""


def _bounded_int(raw, default, low, high, label):
    if raw in (None, ""):
        return default, ""
    try:
        value = int(raw)
    except (TypeError, ValueError):
        return default, f"{label} không hợp lệ."
    if not low <= value <= high:
        return default, f"{label} phải từ {low} đến {high}."
    return value, ""


def _optional_department(raw, departments):
    if not raw:
        return None, False
    try:
        phong_id = int(raw)
    except (TypeError, ValueError):
        return None, True
    for department in departments:
        if department.pk == phong_id:
            return department, False
    return None, True


def _search_period(raw, year):
    if not raw:
        return None, ""
    if raw.startswith("thang-"):
        month = raw.removeprefix("thang-")
        try:
            month_number = int(month)
        except (TypeError, ValueError):
            return None, "Kỳ báo cáo không hợp lệ."
        if not 1 <= month_number <= 12:
            return None, "Tháng phải từ 1 đến 12."
        return (
            resolve_period(KIND_MONTH, year, month=month_number),
            "",
        )
    if raw.startswith("quy-"):
        quarter = raw.removeprefix("quy-")
        try:
            quarter_number = int(quarter)
        except (TypeError, ValueError):
            return None, "Kỳ báo cáo không hợp lệ."
        if not 1 <= quarter_number <= 4:
            return None, "Quý phải từ 1 đến 4."
        return (
            resolve_period(KIND_QUARTER, year, quarter=quarter_number),
            "",
        )
    return None, "Kỳ báo cáo không hợp lệ."


def _search_departments(user):
    return list(
        scoped(
            user,
            PhongBan.objects.filter(dang_su_dung=True),
            "id",
        ).order_by("ma_phong")
    )


def _search_activity_types(departments):
    return LoaiHoatDong.objects.filter(
        phong_id__in=[department.pk for department in departments]
    ).select_related("phong").order_by("phong__ma_phong", "ten_loai")


def _search_phieu_period_q(period):
    months = [month for _year, month in months_in_period(period)]
    return (
        Q(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong__tu_ngay__lte=period.end,
            hoat_dong__den_ngay__gte=period.start,
        )
        | Q(
            loai_phieu=LoaiPhieu.THANG,
            ky__nam=period.year,
            ky__so_ky__in=months,
        )
        | Q(
            loai_phieu=LoaiPhieu.DU_AN,
            du_an__nam=period.year,
        )
    )


def _search_phieu_year_q(year):
    return (
        Q(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong__tu_ngay__year=year,
        )
        | Q(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong__den_ngay__year=year,
        )
        | Q(loai_phieu=LoaiPhieu.THANG, ky__nam=year)
        | Q(loai_phieu=LoaiPhieu.DU_AN, du_an__nam=year)
    )


def _query_without_pages(request):
    params = request.GET.copy()
    params.pop("trang_hd", None)
    params.pop("trang_phieu", None)
    return params.urlencode()


def _build_search_context(request, user):
    departments = _search_departments(user)
    year, year_error = _search_year(request.GET.get("year"))
    ky_raw = (request.GET.get("ky") or "").strip()
    period, period_error = _search_period(ky_raw, year)
    selected_department, scope_blocked = _optional_department(
        (request.GET.get("phong") or "").strip(),
        departments,
    )
    selected_type = None
    type_raw = (request.GET.get("loai") or "").strip()
    if type_raw:
        try:
            type_id = int(type_raw)
        except (TypeError, ValueError):
            scope_blocked = True
        else:
            selected_type = (
                LoaiHoatDong.objects.filter(
                    pk=type_id,
                    phong_id__in=[department.pk for department in departments],
                )
                .select_related("phong")
                .first()
            )
            if selected_type is None:
                scope_blocked = True

    selected_linh_vuc = None
    linh_vuc_raw = (request.GET.get("linh_vuc") or "").strip()
    if linh_vuc_raw:
        try:
            linh_vuc_id = int(linh_vuc_raw)
        except (TypeError, ValueError):
            selected_linh_vuc = None
            scope_blocked = True
        else:
            selected_linh_vuc = DanhMucLinhVuc.objects.filter(
                pk=linh_vuc_id
            ).first()
            if selected_linh_vuc is None:
                scope_blocked = True

    ten = (request.GET.get("ten") or "").strip()
    don_vi = (request.GET.get("don_vi") or "").strip()

    activities = scoped(
        user,
        HoatDong.objects.select_related(
            "loai_hoat_dong",
            "loai_hoat_dong__phong",
            "linh_vuc",
        ).prefetch_related("don_vi_tham_gia__don_vi"),
        "loai_hoat_dong__phong_id",
    )
    phieus = scoped(
        user,
        PhieuNhapLieu.objects.select_related(
            "phong",
            "hoat_dong",
            "hoat_dong__loai_hoat_dong",
            "hoat_dong__linh_vuc",
            "ky",
            "du_an",
            "nguoi_nhap",
        ).prefetch_related("so_lieu__chi_tieu"),
        "phong_id",
    )
    if scope_blocked:
        activities = activities.none()
        phieus = phieus.none()
    if selected_department is not None:
        activities = activities.filter(
            loai_hoat_dong__phong=selected_department
        )
        phieus = phieus.filter(phong=selected_department)
    if selected_type is not None:
        activities = activities.filter(loai_hoat_dong=selected_type)
        phieus = phieus.filter(hoat_dong__loai_hoat_dong=selected_type)
    if year:
        activities = activities.filter(
            Q(tu_ngay__year=year) | Q(den_ngay__year=year)
        )
        phieus = phieus.filter(_search_phieu_year_q(year))
    if period is not None:
        activities = activities.filter(
            tu_ngay__lte=period.end,
            den_ngay__gte=period.start,
        )
        phieus = phieus.filter(_search_phieu_period_q(period))
    if ten:
        activities = activities.filter(ten__icontains=ten)
        phieus = phieus.filter(
            Q(hoat_dong__ten__icontains=ten)
            | Q(du_an__ten_du_an__icontains=ten)
            | Q(so_lieu__chi_tieu__ten_chi_tieu__icontains=ten)
            | Q(so_lieu__chi_tieu__ma_chi_tieu__icontains=ten)
        )
    if don_vi:
        activities = activities.filter(
            don_vi_tham_gia__don_vi__ten_don_vi__icontains=don_vi
        )
        phieus = phieus.filter(
            hoat_dong__don_vi_tham_gia__don_vi__ten_don_vi__icontains=don_vi
        )
    if selected_linh_vuc is not None:
        activities = activities.filter(linh_vuc=selected_linh_vuc)
        phieus = phieus.filter(
            Q(hoat_dong__linh_vuc=selected_linh_vuc)
            | Q(so_lieu__linh_vuc=selected_linh_vuc)
        )

    activities = activities.distinct().order_by("-tu_ngay", "-id")
    phieus = phieus.distinct().order_by("-id")
    activity_page = Paginator(activities, SEARCH_PAGE_SIZE).get_page(
        request.GET.get("trang_hd")
    )
    phieu_page = Paginator(phieus, SEARCH_PAGE_SIZE).get_page(
        request.GET.get("trang_phieu")
    )
    for phieu in phieu_page.object_list:
        lines = list(phieu.so_lieu.all())
        phieu.so_lieu_count = len(lines)
        phieu.so_lieu_hien_thi = [
            {
                "ten": line.chi_tieu.ten_chi_tieu,
                "gia_tri": format_vi_number(line.gia_tri),
                "don_vi": line.chi_tieu.don_vi_tinh,
            }
            for line in lines[:3]
        ]

    errors = [
        message
        for message in (year_error, period_error)
        if message
    ]
    if scope_blocked:
        errors.append(
            "Phạm vi lọc nằm ngoài quyền xem. Không có kết quả nào được hiển thị."
        )

    return {
        "mode": "tra_cuu",
        "departments": departments,
        "activity_types": _search_activity_types(departments),
        "linh_vucs": DanhMucLinhVuc.objects.order_by(
            "he_thong",
            "ma",
        ),
        "period_choices": SEARCH_PERIOD_CHOICES,
        "year_options": range(today().year - 5, today().year + 2),
        "activity_page": activity_page,
        "phieu_page": phieu_page,
        "search_query": _query_without_pages(request),
        "errors": errors,
        "filters": {
            "year": year,
            "ky": ky_raw,
            "phong": (
                str(selected_department.pk)
                if selected_department is not None
                else ""
            ),
            "loai": (
                str(selected_type.pk) if selected_type is not None else ""
            ),
            "ten": ten,
            "don_vi": don_vi,
            "linh_vuc": (
                str(selected_linh_vuc.pk)
                if selected_linh_vuc is not None
                else ""
            ),
        },
    }


def _comparison_rows(rows_a, rows_b):
    merged = {}
    for row in rows_a:
        merged[(row.chi_tieu_id, row.phong_id)] = {
            "row_a": row,
            "row_b": None,
        }
    for row in rows_b:
        key = (row.chi_tieu_id, row.phong_id)
        item = merged.setdefault(key, {"row_a": None, "row_b": None})
        item["row_b"] = row

    result = []
    for key in sorted(merged):
        item = merged[key]
        row = item["row_a"] or item["row_b"]
        value_a = item["row_a"].period_value if item["row_a"] else None
        value_b = item["row_b"].period_value if item["row_b"] else None
        if value_a is None and value_b is None:
            difference = None
        else:
            difference = (value_b or Decimal("0")) - (
                value_a or Decimal("0")
            )
        result.append(
            {
                "chi_tieu_id": row.chi_tieu_id,
                "ma_chi_tieu": row.ma_chi_tieu,
                "ten_chi_tieu": row.ten_chi_tieu,
                "don_vi_tinh": row.don_vi_tinh,
                "ma_phong": row.ma_phong,
                "ten_phong": row.ten_phong,
                "value_a": format_vi_number(value_a),
                "value_b": format_vi_number(value_b),
                "difference": format_vi_number(difference),
            }
        )
    result.sort(key=lambda item: (item["ma_phong"], item["ma_chi_tieu"]))
    return result


def _build_comparison_context(request, user):
    departments = allowed_departments(user)
    visible_ids = {department.pk for department in departments}
    kind = (
        KIND_QUARTER
        if request.GET.get("kind") == KIND_QUARTER
        else KIND_MONTH
    )
    current = today()
    month, month_error = _bounded_int(
        request.GET.get("month"),
        current.month,
        1,
        12,
        "Tháng",
    )
    quarter, quarter_error = _bounded_int(
        request.GET.get("quarter"),
        (current.month - 1) // 3 + 1,
        1,
        4,
        "Quý",
    )
    year_a, year_a_error = _bounded_int(
        request.GET.get("year_a"),
        current.year - 1,
        2000,
        2100,
        "Năm A",
    )
    year_b, year_b_error = _bounded_int(
        request.GET.get("year_b"),
        current.year,
        2000,
        2100,
        "Năm B",
    )
    selected_department, scope_blocked = _optional_department(
        (request.GET.get("phong") or "").strip(),
        departments,
    )
    if (
        selected_department is None
        and not (request.GET.get("phong") or "").strip()
        and _is_scoped(user)
        and departments
    ):
        selected_department = departments[0]

    period_a = resolve_period(
        kind,
        year_a,
        month=month if kind == KIND_MONTH else None,
        quarter=quarter if kind == KIND_QUARTER else None,
    )
    period_b = resolve_period(
        kind,
        year_b,
        month=month if kind == KIND_MONTH else None,
        quarter=quarter if kind == KIND_QUARTER else None,
    )
    department_id = (
        selected_department.pk
        if selected_department is not None
        else None
    )
    if scope_blocked:
        rows_a = []
        rows_b = []
    else:
        rows_a = rollup(period_a, department_id=department_id)
        rows_b = rollup(period_b, department_id=department_id)
        rows_a = [row for row in rows_a if row.phong_id in visible_ids]
        rows_b = [row for row in rows_b if row.phong_id in visible_ids]

    errors = [
        message
        for message in (
            month_error,
            quarter_error,
            year_a_error,
            year_b_error,
        )
        if message
    ]
    if scope_blocked:
        errors.append(
            "Phạm vi lọc nằm ngoài quyền xem. Không có kết quả nào được hiển thị."
        )
    if scope_blocked:
        scope_label = "Phạm vi không được phép"
    elif selected_department is not None:
        scope_label = (
            f"{selected_department.ma_phong} — "
            f"{selected_department.ten_phong}"
        )
    else:
        scope_label = "Toàn trung tâm"

    return {
        "mode": "so_sanh",
        "departments": departments,
        "can_choose_center": not _is_scoped(user),
        "month_options": range(1, 13),
        "quarter_options": range(1, 5),
        "comparison_rows": _comparison_rows(rows_a, rows_b),
        "comparison": {
            "kind": kind,
            "month": month,
            "quarter": quarter,
            "year_a": year_a,
            "year_b": year_b,
            "phong": (
                str(selected_department.pk)
                if selected_department is not None
                else ""
            ),
            "scope_label": scope_label,
            "period_a_label": period_label(period_a),
            "period_b_label": period_label(period_b),
        },
        "errors": errors,
    }


@login_required
@require_http_methods(["GET"])
def lich_su(request):
    if not can(request.user, "view_history"):
        raise PermissionDenied
    mode = request.GET.get("che_do", "tra_cuu")
    if mode == "so_sanh":
        context = _build_comparison_context(request, request.user)
    else:
        context = _build_search_context(request, request.user)
    return render(request, "reporting/lich_su.html", context)


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
