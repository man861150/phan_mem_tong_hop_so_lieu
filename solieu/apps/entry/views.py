"""Data-entry forms, indicator rows, project support, and approvals."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.http import Http404
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import (
    require_http_methods,
    require_POST,
)

from apps.accounts.permissions import can
from apps.accounts.scoping import scoped
from apps.activities.models import DuAn, HoatDong, TrangThaiHoatDong
from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    CountSubject,
    KieuGhiNhan,
    KyBaoCao,
    PhongBan,
    TrangThaiKy,
)
from apps.entry.forms import (
    SOURCE_SURVEY,
    ActivityEntryForm,
    AdHocForm,
    HoTroDuAnForm,
    MonthlyEntryForm,
)
from apps.entry.models import (
    HoTroDuAn,
    LoaiPhieu,
    PhieuNhapLieu,
    TrangThaiPhieu,
)
from apps.reporting.rollup import ReportPeriod, rollup


def _require_view(user):
    if not (can(user, "edit_entry") or can(user, "view_progress")):
        raise PermissionDenied


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
        phieu = PhieuNhapLieu.objects.create(
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
        phieu = PhieuNhapLieu.objects.create(
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
        phieu = PhieuNhapLieu.objects.create(
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
    can_edit = can(request.user, "edit_entry", activity.phong.pk)
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
        "form": form,
        "phieu": phieu,
        "phieus": phieus,
        "rows": rows,
        "has_split_grids": has_split_grids,
        "can_delete": (
            phieu is not None
            and can_edit
            and phieu.trang_thai
            in (TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI)
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


@login_required
@require_http_methods(["GET", "POST"])
def phieu_hoat_dong(request, hoat_dong_id):
    _require_view(request.user)
    activity = get_object_or_404(
        _activity_queryset(request.user),
        pk=hoat_dong_id,
    )
    can_edit = can(request.user, "edit_entry", activity.phong.pk)
    organized = activity.trang_thai == TrangThaiHoatDong.DA_TO_CHUC

    if not organized:
        if request.method == "POST":
            raise PermissionDenied
        return _render_activity(request, activity)

    phieu_id = request.GET.get("phieu")
    phieu = _get_activity_phieu(activity, phieu_id)
    if phieu is None and can_edit:
        phieu = _ensure_activity_phieu(activity, request.user)

    if request.method == "POST" and not can_edit:
        raise PermissionDenied

    if activity.la_nhiem_vu_phat_sinh:
        form = AdHocForm(request.POST or None, instance=activity)
        if request.method == "POST" and form.is_valid():
            form.save()
            messages.success(request, "Đã lưu nội dung nhiệm vụ phát sinh.")
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
        form.save(phieu)
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
    if phieu.trang_thai not in (
        TrangThaiPhieu.NHAP,
        TrangThaiPhieu.TRA_LAI,
    ):
        raise PermissionDenied
    target = _delete_redirect(phieu)
    phieu.delete()
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
    if request.user.phong_id:
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
    can_edit = period_open and can(
        request.user,
        "edit_entry",
        phong.pk,
    )
    phieu = _month_phieu(phong, ky)
    if phieu is None and can_edit:
        phieu = _ensure_month_phieu(phong, ky, request.user)

    if request.method == "POST" and not can_edit:
        raise PermissionDenied

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
        form.save(phieu)
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
            "period_open": period_open,
            "can_delete": (
                phieu is not None
                and can_edit
                and phieu.trang_thai
                in (TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI)
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
    can_edit = can(request.user, "edit_entry", project.phong_id)
    phieu = _project_phieu(project)
    if phieu is None and can_edit:
        phieu = _ensure_project_phieu(project, request.user)

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
            "can_delete": (
                phieu is not None
                and can_edit
                and phieu.trang_thai
                in (TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI)
            ),
        },
    )
