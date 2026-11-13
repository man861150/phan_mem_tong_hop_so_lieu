"""Data-entry forms, indicator rows, project support, and approvals."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.db import IntegrityError, transaction
from django.db.models import Q
from django.http import Http404, HttpResponseBadRequest, JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
)

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES
from apps.accounts.scoping import scoped
from apps.activities.models import DuAn, HoatDong, TrangThaiHoatDong
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    CountSubject,
    DanhMucLinhVuc,
    HeThongLinhVuc,
    KieuGhiNhan,
    KyBaoCao,
    PhongBan,
    TrangThaiKy,
)
from apps.entry import workflow
from apps.entry.forms import (
    SOURCE_SURVEY,
    ActivityEntryForm,
    AdHocForm,
    HoTroDuAnForm,
    MonthlyEntryForm,
    WorkflowCommentForm,
)
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)
from apps.reporting.formatting import format_vi_number
from apps.reporting.rollup import ReportPeriod, rollup


def _require_view(user):
    if not (can(user, "edit_entry") or can(user, "view_progress")):
        raise PermissionDenied


@login_required
@require_http_methods(["GET"])
def linh_vuc_search(request):
    """Search the shared field tree for one picker, at most 20 rows."""
    _require_view(request.user)
    he_thong = request.GET.get("he_thong", "")
    if he_thong not in HeThongLinhVuc.values:
        return JsonResponse({"results": []})
    query = request.GET.get("q", "").strip()
    if not query:
        return JsonResponse({"results": []})
    rows = (
        DanhMucLinhVuc.objects.filter(he_thong=he_thong)
        .filter(Q(ma__icontains=query) | Q(ten__icontains=query))
        .order_by("ma")[:20]
    )
    return JsonResponse(
        {
            "results": [
                {"id": row.pk, "ma": row.ma, "ten": row.ten}
                for row in rows
            ]
        }
    )


def _phieu_queryset(user):
    return scoped(
        user,
        PhieuNhapLieu.objects.select_related(
            "phong",
            "hoat_dong",
            "ky",
            "du_an",
            "nguoi_nhap",
        ),
        "phong_id",
    )


EDITABLE_STATUSES = (TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI)

PERIOD_CLOSED_MESSAGE = workflow.PERIOD_CLOSED_MESSAGE
PHIEU_PROCESSED_MESSAGE = workflow.PHIEU_PROCESSED_MESSAGE


def _create_primary_phieu(lookup, **fields):
    """Insert one primary phiếu, or return the one that won a race.

    ``ValidatingModel.save()`` runs ``full_clean()``, so a duplicate primary
    can raise ``ValidationError`` before PostgreSQL reports ``IntegrityError``.
    Both mean another request inserted the winner first.  The nested atomic
    block uses a savepoint so the caller's transaction can continue.
    """
    try:
        with transaction.atomic():
            return PhieuNhapLieu.objects.create(**fields)
    except (IntegrityError, ValidationError):
        phieu = lookup()
        if phieu is not None:
            return phieu
        raise


def _lock_for_write(phieu_id, ky_id=None):
    """Lock the period (when present) then the phiếu, and re-read statuses.

    Returns ``(period, phiếu, refusal)``.  A non-null ``refusal`` means the
    caller must write nothing and show that sentence.  Callers run this inside
    ``transaction.atomic()``.
    """
    ky = None
    if ky_id is not None:
        ky = KyBaoCao.objects.select_for_update().get(pk=ky_id)
        if ky.trang_thai == TrangThaiKy.KHOA:
            return ky, None, PERIOD_CLOSED_MESSAGE
    phieu = PhieuNhapLieu.objects.select_for_update().get(pk=phieu_id)
    if phieu.trang_thai not in EDITABLE_STATUSES:
        return ky, phieu, PHIEU_PROCESSED_MESSAGE
    return ky, phieu, None


def _status_is_editable(phieu):
    return phieu is None or phieu.trang_thai in EDITABLE_STATUSES


def _last_return(phieu):
    if phieu is None:
        return None
    return (
        phieu.lich_su_xu_ly.filter(hanh_dong=HanhDongXuLy.TRA_LAI)
        .select_related("nguoi_xu_ly")
        .order_by("-thoi_diem", "-id")
        .first()
    )


def _activity_queryset(user):
    return scoped(
        user,
        HoatDong.objects.select_related(
            "loai_hoat_dong",
            "loai_hoat_dong__phong",
        ),
        "loai_hoat_dong__phong_id",
    )


def _project_queryset(user):
    return scoped(
        user,
        DuAn.objects.select_related("phong"),
        "phong_id",
    )


def _activity_phieus(activity):
    return PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.HOAT_DONG,
        hoat_dong=activity,
    ).order_by("id")


def _get_activity_phieu(activity, phieu_id=None):
    queryset = _activity_phieus(activity)
    if phieu_id:
        if not str(phieu_id).isdigit():
            raise Http404("Phiếu nhập liệu không hợp lệ.")
        return get_object_or_404(queryset, pk=int(phieu_id))
    primary = queryset.filter(la_phieu_bo_sung=False).first()
    return primary or queryset.first()


def _ensure_activity_phieu(activity, user, *, bo_sung=False):
    if bo_sung:
        return PhieuNhapLieu.objects.create(
            phong=activity.phong,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            la_phieu_bo_sung=True,
            trang_thai=TrangThaiPhieu.NHAP,
            nguoi_nhap=user,
        )
    queryset = _activity_phieus(activity).filter(la_phieu_bo_sung=False)
    phieu = queryset.first()
    if phieu is None:
        phieu = _create_primary_phieu(
            lambda: _activity_phieus(activity)
            .filter(la_phieu_bo_sung=False)
            .first(),
            phong=activity.phong,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            la_phieu_bo_sung=False,
            trang_thai=TrangThaiPhieu.NHAP,
            nguoi_nhap=user,
        )
    return phieu


def _month_phieu(phong, ky):
    return PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.THANG,
        phong=phong,
        ky=ky,
        la_phieu_bo_sung=False,
    ).order_by("id").first()


def _ensure_month_phieu(phong, ky, user):
    phieu = _month_phieu(phong, ky)
    if phieu is None:
        phieu = _create_primary_phieu(
            lambda: _month_phieu(phong, ky),
            phong=phong,
            loai_phieu=LoaiPhieu.THANG,
            ky=ky,
            la_phieu_bo_sung=False,
            trang_thai=TrangThaiPhieu.NHAP,
            nguoi_nhap=user,
        )
    return phieu


def _project_phieu(du_an):
    return PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.DU_AN,
        du_an=du_an,
        la_phieu_bo_sung=False,
    ).order_by("id").first()


def _ensure_project_phieu(du_an, user):
    phieu = _project_phieu(du_an)
    if phieu is None:
        phieu = _create_primary_phieu(
            lambda: _project_phieu(du_an),
            phong=du_an.phong,
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=du_an,
            la_phieu_bo_sung=False,
            trang_thai=TrangThaiPhieu.NHAP,
            nguoi_nhap=user,
        )
    return phieu


def _activity_url(activity, phieu=None):
    url = reverse("entry:phieu_hoat_dong", args=[activity.pk])
    if phieu is not None:
        url = f"{url}?phieu={phieu.pk}"
    return url


def _activity_period(activity):
    anchor = activity.den_ngay or activity.tu_ngay
    return ReportPeriod.month(anchor.year, anchor.month)


def _count_badges(activity):
    period = _activity_period(activity)
    rows = rollup(period, department_id=activity.phong.pk)
    by_indicator = {row.chi_tieu_id: row for row in rows}
    indicators = ChiTieu.objects.filter(
        cach_tong_hop=CachTongHop.COUNT,
        count_subject=CountSubject.ACTIVITY,
        loai_hoat_dong=activity.loai_hoat_dong,
        dang_su_dung=True,
    ).order_by("ma_chi_tieu")
    badges = []
    for indicator in indicators:
        row = by_indicator.get(indicator.pk)
        badges.append(
            {
                "chi_tieu": indicator,
                "official": row.period_value if row is not None else None,
                "plan": row.plan if row is not None else None,
            }
        )
    return badges, period


def _status_counts(activity, period):
    queryset = HoatDong.objects.filter(
        loai_hoat_dong=activity.loai_hoat_dong,
        tu_ngay__gte=period.start,
        tu_ngay__lte=period.end,
    )
    return (
        queryset.filter(trang_thai=TrangThaiHoatDong.DA_TO_CHUC).count(),
        queryset.count(),
    )


def _render_activity(
    request,
    activity,
    *,
    form=None,
    phieu=None,
    rows=None,
    extra=None,
):
    has_edit_permission = can(
        request.user,
        "edit_entry",
        activity.phong.pk,
    )
    can_edit = has_edit_permission and _status_is_editable(phieu)
    organized = activity.trang_thai == TrangThaiHoatDong.DA_TO_CHUC
    phieus = list(_activity_phieus(activity)) if organized else []
    rows = rows or []
    has_split_grids = any(
        row.get("has_object") or row.get("has_linh_vuc") for row in rows
    )
    context = {
        "activity": activity,
        "organized": organized,
        "can_edit": can_edit,
        "can_submit": can_edit and phieu is not None,
        "locked": phieu is not None and not _status_is_editable(phieu),
        "form": form,
        "phieu": phieu,
        "phieus": phieus,
        "rows": rows,
        "has_split_grids": has_split_grids,
        "last_return": _last_return(phieu),
        "can_delete": (
            phieu is not None
            and can_edit
            and phieu.trang_thai in EDITABLE_STATUSES
        ),
    }
    if organized:
        badges, period = _count_badges(activity)
        status_count, status_total = _status_counts(activity, period)
        context.update(
            {
                "count_badges": badges,
                "status_count": status_count,
                "status_total": status_total,
                "period_label": f"Tháng {period.start.month}/{period.year}",
            }
        )
    if extra:
        context.update(extra)
    return render(request, "entry/phieu_form.html", context)


def _submit_entry_form(form, phieu, user):
    """Validate a bound entry form and submit it inside the workflow lock."""
    try:
        form.validate_required()
    except ValidationError as exc:
        for field, errors in exc.message_dict.items():
            form.add_error(field, errors)
        return False
    try:
        workflow.submit(
            phieu,
            user,
            apply=lambda locked: form.save(locked),
        )
    except ValidationError as exc:
        form.add_error(None, exc.messages)
        return False
    return True


@login_required
@require_http_methods(["GET", "POST"])
def phieu_hoat_dong(request, hoat_dong_id):
    _require_view(request.user)
    activity = get_object_or_404(
        _activity_queryset(request.user),
        pk=hoat_dong_id,
    )
    has_edit_permission = can(
        request.user,
        "edit_entry",
        activity.phong.pk,
    )
    organized = activity.trang_thai == TrangThaiHoatDong.DA_TO_CHUC

    if not organized:
        if request.method == "POST":
            raise PermissionDenied
        return _render_activity(request, activity)

    phieu_id = request.GET.get("phieu")
    phieu = _get_activity_phieu(activity, phieu_id)
    if phieu is None and has_edit_permission:
        phieu = _ensure_activity_phieu(activity, request.user)

    can_edit = has_edit_permission and _status_is_editable(phieu)
    if request.method == "POST" and not can_edit:
        raise PermissionDenied

    action = request.POST.get("action", "save")
    if activity.la_nhiem_vu_phat_sinh:
        form = AdHocForm(request.POST or None, instance=activity)
        if request.method == "POST" and form.is_valid():
            if action == "gui":
                try:
                    workflow.submit(
                        phieu,
                        request.user,
                        apply=lambda locked: form.save(),
                    )
                except workflow.InvalidTransition as exc:
                    return HttpResponseBadRequest(str(exc))
                messages.success(
                    request,
                    "Đã gửi duyệt phiếu nhiệm vụ phát sinh.",
                )
            else:
                with transaction.atomic():
                    _ky, _locked, refusal = _lock_for_write(phieu.pk)
                    if refusal:
                        messages.error(request, refusal)
                        return redirect(_activity_url(activity, phieu))
                    form.save()
                messages.success(
                    request,
                    "Đã lưu nội dung nhiệm vụ phát sinh.",
                )
            return redirect(_activity_url(activity, phieu))
        return _render_activity(
            request,
            activity,
            form=form,
            phieu=phieu,
            extra={"ad_hoc": True},
        )

    form = ActivityEntryForm(
        request.POST or None,
        activity=activity,
        phieu=phieu,
        default_nguon_name=(
            SOURCE_SURVEY
            if phieu is not None and phieu.la_phieu_bo_sung
            else None
        ),
    )
    if request.method == "POST" and form.is_valid():
        if action == "gui":
            try:
                submitted = _submit_entry_form(form, phieu, request.user)
            except workflow.InvalidTransition as exc:
                return HttpResponseBadRequest(str(exc))
            if submitted:
                messages.success(request, "Đã gửi duyệt phiếu kết quả.")
                return redirect(_activity_url(activity, phieu))
        else:
            with transaction.atomic():
                _ky, locked, refusal = _lock_for_write(phieu.pk)
                if refusal:
                    messages.error(request, refusal)
                    return redirect(_activity_url(activity, phieu))
                form.save(locked)
            messages.success(request, "Đã lưu nháp phiếu kết quả.")
            return redirect(_activity_url(activity, phieu))
    return _render_activity(
        request,
        activity,
        form=form,
        phieu=phieu,
        rows=form.presentation_rows(),
        extra={"ad_hoc": False},
    )


@login_required
@require_POST
def phieu_hoat_dong_bo_sung(request, hoat_dong_id):
    _require_view(request.user)
    activity = get_object_or_404(
        _activity_queryset(request.user),
        pk=hoat_dong_id,
    )
    if not can(request.user, "edit_entry", activity.phong.pk):
        raise PermissionDenied
    if activity.trang_thai != TrangThaiHoatDong.DA_TO_CHUC:
        raise PermissionDenied
    if activity.la_nhiem_vu_phat_sinh:
        raise PermissionDenied
    if _get_activity_phieu(activity) is None:
        _ensure_activity_phieu(activity, request.user)
    phieu = _ensure_activity_phieu(activity, request.user, bo_sung=True)
    messages.success(request, "Đã tạo phiếu bổ sung.")
    return redirect(_activity_url(activity, phieu))


@login_required
@require_POST
def phieu_xoa(request, phieu_id):
    _require_view(request.user)
    phieu = get_object_or_404(_phieu_queryset(request.user), pk=phieu_id)
    if not can(request.user, "edit_entry", phieu.phong_id):
        raise PermissionDenied
    ky_id = phieu.ky_id if phieu.loai_phieu == LoaiPhieu.THANG else None
    with transaction.atomic():
        _ky, locked, refusal = _lock_for_write(phieu.pk, ky_id)
        if refusal:
            messages.error(request, refusal)
            return redirect(_delete_redirect(phieu))
        target = _delete_redirect(locked)
        locked.delete()
    messages.success(request, "Đã xóa phiếu nháp và toàn bộ số liệu của phiếu.")
    return redirect(target)


def _delete_redirect(phieu):
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        return reverse(
            "activities:hoat_dong_detail",
            args=[phieu.hoat_dong_id],
        )
    if phieu.loai_phieu == LoaiPhieu.THANG and phieu.ky_id:
        return reverse("entry:phieu_thang", args=[phieu.ky_id])
    if phieu.loai_phieu == LoaiPhieu.DU_AN and phieu.du_an_id:
        return reverse("entry:phieu_du_an", args=[phieu.du_an_id])
    return reverse("home")


def _month_rollup_values(phong, ky):
    current_period = ReportPeriod.month(ky.nam, ky.so_ky)
    if ky.so_ky == 1:
        previous_period = ReportPeriod.month(ky.nam - 1, 12)
    else:
        previous_period = ReportPeriod.month(ky.nam, ky.so_ky - 1)
    current_rows = rollup(current_period, department_id=phong.pk)
    previous_rows = rollup(previous_period, department_id=phong.pk)
    previous_values = {
        row.chi_tieu_id: row.period_value for row in previous_rows
    }
    cumulative_values = {
        row.chi_tieu_id: row.cumulative for row in current_rows
    }
    current_by_indicator = {
        row.chi_tieu_id: row for row in current_rows
    }
    return previous_values, cumulative_values, current_by_indicator


@login_required
@require_http_methods(["GET"])
def phieu_thang_chon(request):
    """List reporting periods, open months first, then open one month."""
    _require_view(request.user)
    is_scoped = request.user.role in SCOPED_ROLES
    phong = getattr(request.user, "phong", None) if is_scoped else None
    periods = sorted(
        KyBaoCao.objects.all(),
        key=lambda ky: (
            ky.trang_thai != TrangThaiKy.MO,
            -ky.nam,
            -ky.so_ky,
        ),
    )
    rows = []
    for ky in periods:
        phieu = _month_phieu(phong, ky) if phong is not None else None
        rows.append(
            {
                "ky": ky,
                "is_open": ky.trang_thai == TrangThaiKy.MO,
                "phieu": phieu,
            }
        )
    return render(
        request,
        "entry/phieu_thang_chon.html",
        {
            "periods": rows,
            "is_scoped": is_scoped,
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def phieu_thang(request, ky_id):
    _require_view(request.user)
    ky = get_object_or_404(KyBaoCao, pk=ky_id)
    visible_phong = scoped(
        request.user,
        PhongBan.objects.filter(dang_su_dung=True),
        "id",
    ).order_by("ma_phong")

    phong = None
    if request.user.role in SCOPED_ROLES and request.user.phong_id:
        phong = visible_phong.filter(pk=request.user.phong_id).first()
    else:
        phong_value = request.GET.get("phong", "")
        if phong_value:
            if not phong_value.isdigit():
                raise Http404("Phòng ban không hợp lệ.")
            phong = visible_phong.filter(pk=int(phong_value)).first()
            if phong is None:
                raise Http404("Không tìm thấy phòng ban.")

    if phong is None:
        return render(
            request,
            "entry/phieu_thang.html",
            {
                "ky": ky,
                "phong": None,
                "form": None,
                "rows": [],
                "derived_rows": [],
                "phong_options": visible_phong,
                "can_edit": False,
                "period_open": ky.trang_thai == TrangThaiKy.MO,
            },
        )

    period_open = ky.trang_thai == TrangThaiKy.MO
    has_edit_permission = can(
        request.user,
        "edit_entry",
        phong.pk,
    )
    phieu = _month_phieu(phong, ky)
    if phieu is None and period_open and has_edit_permission:
        phieu = _ensure_month_phieu(phong, ky, request.user)

    can_edit = (
        period_open
        and has_edit_permission
        and _status_is_editable(phieu)
    )
    if request.method == "POST" and not can_edit:
        raise PermissionDenied

    action = request.POST.get("action", "save")
    previous_values, cumulative_values, current_by_indicator = (
        _month_rollup_values(phong, ky)
    )
    form = MonthlyEntryForm(
        request.POST or None,
        phong=phong,
        ky=ky,
        phieu=phieu,
        previous_values=previous_values,
        cumulative_values=cumulative_values,
    )
    if request.method == "POST" and form.is_valid():
        with transaction.atomic():
            _ky_locked, locked, refusal = _lock_for_write(phieu.pk, ky.pk)
            if refusal:
                messages.error(request, refusal)
                return redirect("entry:phieu_thang", ky_id=ky.pk)
            if action == "gui":
                try:
                    submitted = _submit_entry_form(
                        form,
                        locked,
                        request.user,
                    )
                except workflow.InvalidTransition as exc:
                    return HttpResponseBadRequest(str(exc))
            else:
                form.save(locked)
                submitted = False
        if action == "gui":
            if submitted:
                messages.success(request, "Đã gửi duyệt phiếu tháng.")
                return redirect("entry:phieu_thang", ky_id=ky.pk)
        else:
            messages.success(request, "Đã lưu nháp phiếu tháng.")
            return redirect("entry:phieu_thang", ky_id=ky.pk)

    derived = (
        ChiTieu.objects.filter(
            nhom__phong=phong,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
            dang_su_dung=True,
            cach_tong_hop__in=(CachTongHop.RATIO, CachTongHop.COUNT),
        )
        .select_related("nhom")
        .order_by("nhom__thu_tu", "ma_chi_tieu")
    )
    derived_rows = [
        {"chi_tieu": item, "rollup": current_by_indicator.get(item.pk)}
        for item in derived
    ]
    rows = form.presentation_rows()
    has_split_grids = any(
        row.get("has_object") or row.get("has_linh_vuc") for row in rows
    )
    return render(
        request,
        "entry/phieu_thang.html",
        {
            "ky": ky,
            "phong": phong,
            "phieu": phieu,
            "form": form,
            "rows": rows,
            "has_split_grids": has_split_grids,
            "derived_rows": derived_rows,
            "phong_options": visible_phong,
            "can_edit": can_edit,
            "can_submit": can_edit and phieu is not None,
            "locked": phieu is not None and not _status_is_editable(phieu),
            "last_return": _last_return(phieu),
            "period_open": period_open,
            "can_delete": (
                phieu is not None
                and can_edit
                and phieu.trang_thai in EDITABLE_STATUSES
            ),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def phieu_du_an(request, du_an_id):
    _require_view(request.user)
    project = get_object_or_404(
        _project_queryset(request.user),
        pk=du_an_id,
    )
    has_edit_permission = can(
        request.user,
        "edit_entry",
        project.phong_id,
    )
    phieu = _project_phieu(project)
    if phieu is None and has_edit_permission:
        phieu = _ensure_project_phieu(project, request.user)

    can_edit = has_edit_permission and _status_is_editable(phieu)
    if request.method == "POST" and not can_edit:
        raise PermissionDenied

    form = None
    if can_edit and phieu is not None:
        form = HoTroDuAnForm(
            request.POST or None,
            du_an=project,
            phieu=phieu,
        )
        if request.method == "POST" and form.is_valid():
            with transaction.atomic():
                _ky, _locked, refusal = _lock_for_write(phieu.pk)
                if refusal:
                    messages.error(request, refusal)
                    return redirect(
                        "entry:phieu_du_an",
                        du_an_id=project.pk,
                    )
                form.save()
            messages.success(request, "Đã thêm dòng hỗ trợ dự án.")
            return redirect("entry:phieu_du_an", du_an_id=project.pk)

    lines = (
        HoTroDuAn.objects.filter(phieu=phieu, du_an=project)
        .select_related("du_an")
        .order_by("-ngay_ho_tro", "-id")
        if phieu is not None
        else HoTroDuAn.objects.none()
    )
    return render(
        request,
        "entry/phieu_du_an.html",
        {
            "project": project,
            "phieu": phieu,
            "form": form,
            "lines": lines,
            "can_edit": can_edit,
            "can_submit": can_edit and phieu is not None,
            "locked": phieu is not None and not _status_is_editable(phieu),
            "last_return": _last_return(phieu),
            "can_delete": (
                phieu is not None
                and can_edit
                and phieu.trang_thai in EDITABLE_STATUSES
            ),
        },
    )


def _phieu_period(phieu):
    """Return the reporting month used by the detail rollup comparison."""
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        activity = phieu.hoat_dong
        anchor = activity.den_ngay or activity.tu_ngay
        return ReportPeriod.month(anchor.year, anchor.month)
    if phieu.loai_phieu == LoaiPhieu.THANG and phieu.ky_id:
        return ReportPeriod.month(phieu.ky.nam, phieu.ky.so_ky)
    return None


def _previous_period(period):
    if period is None:
        return None
    if period.start.month == 1:
        return ReportPeriod.month(period.year - 1, 12)
    return ReportPeriod.month(period.year, period.start.month - 1)


def _detail_rollup(phieu):
    period = _phieu_period(phieu)
    if period is None:
        return None, {}, {}
    previous_period = _previous_period(period)
    current = {
        row.chi_tieu_id: row
        for row in rollup(period, department_id=phieu.phong_id)
    }
    previous = {
        row.chi_tieu_id: row
        for row in rollup(previous_period, department_id=phieu.phong_id)
    }
    return previous_period, current, previous


def _detail_rows(phieu):
    _period, current, previous = _detail_rollup(phieu)
    rows = (
        phieu.so_lieu.select_related(
            "chi_tieu",
            "doi_tuong",
            "linh_vuc",
            "nguon",
        )
        .order_by("chi_tieu__ma_chi_tieu", "id")
    )
    result = []
    for row in rows:
        current_row = current.get(row.chi_tieu_id)
        previous_row = previous.get(row.chi_tieu_id)
        result.append(
            {
                "row": row,
                "official": (
                    current_row.period_value
                    if current_row is not None
                    else None
                ),
                "previous": (
                    previous_row.period_value
                    if previous_row is not None
                    else None
                ),
            }
        )
    return result


def _render_phieu_detail(request, phieu, **extra):
    can_edit = can(request.user, "edit_entry", phieu.phong_id)
    can_approve = can(request.user, "approve_entry", phieu.phong_id)
    can_approve_role = can(request.user, "approve_entry")
    editable = phieu.trang_thai in EDITABLE_STATUSES
    previous_period, _current, _previous = _detail_rollup(phieu)
    activity = phieu.hoat_dong if phieu.hoat_dong_id else None
    context = {
        "phieu": phieu,
        "target": phieu.hoat_dong or phieu.ky or phieu.du_an,
        "activity": activity,
        "ad_hoc": bool(activity and activity.la_nhiem_vu_phat_sinh),
        "project": phieu.du_an if phieu.du_an_id else None,
        "project_lines": (
            phieu.ho_tro_du_an.select_related("du_an").order_by(
                "-ngay_ho_tro",
                "-id",
            )
            if phieu.loai_phieu == LoaiPhieu.DU_AN
            else []
        ),
        "detail_rows": _detail_rows(phieu),
        "previous_period": previous_period,
        "workflow_history": (
            phieu.lich_su_xu_ly.select_related("nguoi_xu_ly").order_by(
                "thoi_diem",
                "id",
            )
        ),
        "last_return": _last_return(phieu),
        "changes": workflow.changes_since_previous_submit(phieu),
        "can_edit": can_edit and editable,
        "can_submit": can_edit and editable,
        "can_approve_role": can_approve_role,
        "can_approve": can_approve
        and phieu.trang_thai == TrangThaiPhieu.CHO_DUYET,
        "can_return": can_approve
        and phieu.trang_thai == TrangThaiPhieu.CHO_DUYET,
        "can_reopen": can_approve
        and phieu.trang_thai == TrangThaiPhieu.DA_DUYET,
        "can_view_history": can(request.user, "view_history"),
        "comment_form": WorkflowCommentForm(),
    }
    context.update(extra)
    return render(request, "entry/phieu_detail.html", context)


@login_required
def phieu_detail(request, phieu_id):
    _require_view(request.user)
    phieu = get_object_or_404(
        _phieu_queryset(request.user),
        pk=phieu_id,
    )
    return _render_phieu_detail(request, phieu)


HISTORY_FIELDS = ("gia_tri", "doi_tuong", "linh_vuc", "nguon", "ghi_chu")
HISTORY_FK_FIELDS = frozenset({"doi_tuong", "linh_vuc", "nguon"})
HISTORY_TYPE_LABELS = {
    "+": "Thêm",
    "~": "Sửa",
    "-": "Xóa",
}
HISTORY_PAGE_SIZE = 50


def _history_raw(record, field_name):
    if record is None:
        return None
    if field_name in HISTORY_FK_FIELDS:
        return getattr(record, f"{field_name}_id")
    if field_name == "ghi_chu":
        return (getattr(record, field_name) or "").strip()
    return getattr(record, field_name)


def _history_value(record, field_name):
    if record is None:
        return "—"
    if field_name == "gia_tri":
        return format_vi_number(record.gia_tri)
    value = getattr(record, field_name)
    return str(value) if value else "—"


def _history_user(record):
    user = getattr(record, "history_user", None)
    if user is None:
        return "—"
    if user.ho_ten:
        return f"{user.ho_ten} ({user.username})"
    return user.username


def _history_rows(phieu):
    """Diff consecutive simple-history snapshots for every SoLieu row."""
    records = SoLieu.history.filter(phieu_id=phieu.pk).select_related(
        "chi_tieu",
        "doi_tuong",
        "linh_vuc",
        "nguon",
        "history_user",
    )
    previous_by_row = {}
    rows = []
    for record in records.order_by("history_date", "history_id"):
        previous = previous_by_row.get(record.id)
        if record.history_type == "-":
            changed_fields = [
                field_name
                for field_name in HISTORY_FIELDS
                if _history_raw(record, field_name) not in (None, "")
            ]
        elif record.history_type == "+" or previous is None:
            changed_fields = [
                field_name
                for field_name in HISTORY_FIELDS
                if _history_raw(record, field_name) not in (None, "")
            ]
        else:
            changed_fields = [
                field_name
                for field_name in HISTORY_FIELDS
                if _history_raw(previous, field_name)
                != _history_raw(record, field_name)
            ]

        indicator = record.chi_tieu or (
            previous.chi_tieu if previous is not None else None
        )
        for field_name in changed_fields:
            if record.history_type == "-":
                old_record, new_record = record, None
            else:
                old_record, new_record = previous, record
            field = record._meta.get_field(field_name)
            rows.append(
                {
                    "thoi_diem": record.history_date,
                    "nguoi": _history_user(record),
                    "chi_tieu": (
                        indicator.ten_chi_tieu if indicator else "—"
                    ),
                    "ten_truong": field.verbose_name,
                    "cu": _history_value(old_record, field_name),
                    "moi": _history_value(new_record, field_name),
                    "loai": HISTORY_TYPE_LABELS.get(
                        record.history_type,
                        record.history_type,
                    ),
                }
            )
        previous_by_row[record.id] = record
    rows.reverse()
    return rows


@login_required
@require_http_methods(["GET"])
def phieu_lich_su(request, phieu_id):
    if not can(request.user, "view_history"):
        raise PermissionDenied
    phieu = get_object_or_404(
        _phieu_queryset(request.user),
        pk=phieu_id,
    )
    page_obj = Paginator(_history_rows(phieu), HISTORY_PAGE_SIZE).get_page(
        request.GET.get("trang")
    )
    return render(
        request,
        "entry/lich_su_truong.html",
        {
            "phieu": phieu,
            "rows": page_obj.object_list,
            "page_obj": page_obj,
        },
    )


def _get_action_phieu(phieu_id):
    """Load a phiếu for an action; permission is checked by the caller."""
    return get_object_or_404(
        PhieuNhapLieu.objects.select_related(
            "phong",
            "hoat_dong",
            "ky",
            "du_an",
            "nguoi_nhap",
        ),
        pk=phieu_id,
    )


@login_required
@require_POST
def phieu_gui(request, phieu_id):
    _require_view(request.user)
    phieu = _get_action_phieu(phieu_id)
    if not can(request.user, "edit_entry", phieu.phong_id):
        raise PermissionDenied
    if phieu.trang_thai not in EDITABLE_STATUSES:
        return HttpResponseBadRequest(
            "Không thể gửi duyệt phiếu đang ở trạng thái "
            f"{phieu.get_trang_thai_display()}."
        )
    blockers = workflow.submission_errors(phieu)
    if blockers:
        return _render_phieu_detail(
            request,
            phieu,
            action_error="; ".join(blockers),
        )
    try:
        workflow.submit(phieu, request.user)
    except workflow.InvalidTransition as exc:
        return HttpResponseBadRequest(str(exc))
    messages.success(request, "Đã gửi duyệt phiếu.")
    return redirect("entry:phieu_detail", phieu_id=phieu.pk)


@login_required
@require_POST
def phieu_duyet(request, phieu_id):
    _require_view(request.user)
    phieu = _get_action_phieu(phieu_id)
    if not can(request.user, "approve_entry", phieu.phong_id):
        raise PermissionDenied
    try:
        workflow.approve(phieu, request.user)
    except workflow.InvalidTransition as exc:
        return HttpResponseBadRequest(str(exc))
    messages.success(request, "Đã duyệt phiếu.")
    return redirect("entry:phieu_detail", phieu_id=phieu.pk)


@login_required
@require_POST
def phieu_tra_lai(request, phieu_id):
    _require_view(request.user)
    phieu = _get_action_phieu(phieu_id)
    if not can(request.user, "approve_entry", phieu.phong_id):
        raise PermissionDenied
    if phieu.trang_thai != TrangThaiPhieu.CHO_DUYET:
        return HttpResponseBadRequest(
            "Không thể trả lại phiếu đang ở trạng thái "
            f"{phieu.get_trang_thai_display()}."
        )
    form = WorkflowCommentForm(request.POST)
    if not form.is_valid():
        return _render_phieu_detail(
            request,
            phieu,
            comment_form=form,
        )
    try:
        workflow.return_phieu(
            phieu,
            request.user,
            form.cleaned_data["y_kien"],
        )
    except workflow.CommentRequired as exc:
        form.add_error(None, str(exc))
        return _render_phieu_detail(
            request,
            phieu,
            comment_form=form,
        )
    except workflow.InvalidTransition as exc:
        return HttpResponseBadRequest(str(exc))
    messages.success(request, "Đã trả lại phiếu cho cán bộ nhập liệu.")
    return redirect("entry:phieu_detail", phieu_id=phieu.pk)


@login_required
@require_POST
def phieu_mo_lai(request, phieu_id):
    _require_view(request.user)
    phieu = _get_action_phieu(phieu_id)
    if not can(request.user, "approve_entry", phieu.phong_id):
        raise PermissionDenied
    if phieu.trang_thai != TrangThaiPhieu.DA_DUYET:
        return HttpResponseBadRequest(
            "Không thể mở lại phiếu đang ở trạng thái "
            f"{phieu.get_trang_thai_display()}."
        )
    form = WorkflowCommentForm(request.POST)
    if not form.is_valid():
        return _render_phieu_detail(
            request,
            phieu,
            comment_form=form,
        )
    try:
        workflow.reopen(
            phieu,
            request.user,
            form.cleaned_data["y_kien"],
        )
    except workflow.CommentRequired as exc:
        form.add_error(None, str(exc))
        return _render_phieu_detail(
            request,
            phieu,
            comment_form=form,
        )
    except workflow.InvalidTransition as exc:
        return HttpResponseBadRequest(str(exc))
    messages.success(request, "Đã mở lại phiếu để chỉnh sửa.")
    return redirect("entry:phieu_detail", phieu_id=phieu.pk)


@login_required
@require_http_methods(["GET", "POST"])
def duyet_list(request):
    if not can(request.user, "approve_entry"):
        raise PermissionDenied

    queue_queryset = scoped(
        request.user,
        PhieuNhapLieu.objects.filter(
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        ).select_related(
            "phong",
            "hoat_dong",
            "ky",
            "du_an",
            "nguoi_nhap",
        ),
        "phong_id",
    ).order_by("ngay_gui", "id")

    if request.method == "POST":
        approved = 0
        blocked = 0
        selected_ids = {
            int(value)
            for value in request.POST.getlist("phieu_ids")
            if value.isdigit()
        }
        phieus = {
            phieu.pk: phieu
            for phieu in queue_queryset.filter(pk__in=selected_ids)
        }
        for phieu_id in selected_ids:
            phieu = phieus.get(phieu_id)
            if phieu is None:
                blocked += 1
                continue
            if workflow.submission_errors(phieu):
                blocked += 1
                continue
            try:
                workflow.approve(phieu, request.user)
            except (workflow.InvalidTransition, PermissionDenied):
                blocked += 1
            else:
                approved += 1
        messages.success(
            request,
            f"{approved} phiếu đã duyệt, {blocked} phiếu bị chặn.",
        )
        return redirect("entry:duyet_list")

    queue = []
    for phieu in queue_queryset:
        queue.append(
            {
                "phieu": phieu,
                "blockers": workflow.submission_errors(phieu),
            }
        )
    return render(
        request,
        "entry/duyet_list.html",
        {
            "queue": queue,
        },
    )
