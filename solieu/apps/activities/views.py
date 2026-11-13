"""Activity types, activities, partner units, and projects."""

from urllib.parse import urlencode

from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.core.paginator import Paginator
from django.shortcuts import get_object_or_404, redirect, render
from django.utils import timezone
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import can
from apps.accounts.roles import Role
from apps.accounts.scoping import scoped
from apps.activities.forms import DuAnForm, HoatDongForm
from apps.activities.models import (
    DonViPhoiHop,
    DuAn,
    HoatDong,
    TrangThaiHoatDong,
)
from apps.catalog.models import LoaiHoatDong, PhongBan

_UNSCOPED = frozenset({Role.CENTER_HEAD, Role.SYSTEM_ADMIN})
_ACTIVITY_PHONG = "loai_hoat_dong__phong_id"
LIST_PAGE_SIZE = 25


def _require_view(user):
    if not (can(user, "edit_entry") or can(user, "view_progress")):
        raise PermissionDenied


def _departments_for(request):
    visible = scoped(request.user, PhongBan.objects.all(), "id").order_by("ma_phong")
    show_filter = request.user.role in _UNSCOPED
    selected = request.GET.get("phong", "") if show_filter else ""
    departments = visible
    if show_filter and selected:
        departments = visible.filter(ma_phong=selected)
    return visible, departments, show_filter, selected


def _activity_queryset(user):
    queryset = HoatDong.objects.select_related(
        "loai_hoat_dong",
        "loai_hoat_dong__phong",
        "linh_vuc",
    ).prefetch_related(
        "doi_tuong_huong_toi",
        "don_vi_tham_gia__don_vi",
    )
    return scoped(user, queryset, _ACTIVITY_PHONG)


def _get_activity(user, pk):
    return get_object_or_404(_activity_queryset(user), pk=pk)


def _activity_types(departments):
    return LoaiHoatDong.objects.filter(phong_id__in=departments.values("pk")).order_by(
        "phong__ma_phong",
        "ten_loai",
    )


def _selected_don_vi_ids(request, form):
    if request.method == "POST":
        selected = []
        for value in request.POST.getlist("don_vi_phoi_hop"):
            if value.isdigit():
                selected.append(int(value))
        return selected
    if form.instance.pk:
        return list(form.instance.don_vi_tham_gia.values_list("don_vi_id", flat=True))
    return []


def _render_detail(
    request,
    form,
    activity=None,
    can_edit=False,
    selected_don_vi_ids=None,
    transition_errors=None,
):
    if selected_don_vi_ids is None:
        selected_don_vi_ids = (
            [] if form is None else _selected_don_vi_ids(request, form)
        )
    return render(
        request,
        "activities/hoat_dong_form.html",
        {
            "form": form,
            "activity": activity,
            "can_edit": can_edit,
            "don_vi_options": DonViPhoiHop.objects.order_by("ten_don_vi", "id"),
            "selected_don_vi_ids": selected_don_vi_ids,
            "transition_errors": transition_errors,
        },
    )


@login_required
@require_GET
def hoat_dong_list(request):
    _require_view(request.user)
    visible, departments, show_filter, selected_phong = _departments_for(request)
    queryset = _activity_queryset(request.user)
    if show_filter and selected_phong:
        queryset = queryset.filter(loai_hoat_dong__phong__ma_phong=selected_phong)

    loai_hoat_dong = None
    loai_value = request.GET.get("loai", "")
    if loai_value.isdigit():
        loai_hoat_dong = _activity_types(departments).filter(pk=loai_value).first()
        if loai_hoat_dong is not None:
            queryset = queryset.filter(loai_hoat_dong=loai_hoat_dong)

    trang_thai = request.GET.get("trang_thai", "")
    if trang_thai in TrangThaiHoatDong.values:
        queryset = queryset.filter(trang_thai=trang_thai)
    else:
        trang_thai = ""

    ten = request.GET.get("ten", "").strip()
    if ten:
        queryset = queryset.filter(ten__icontains=ten)

    nam = request.GET.get("nam", str(timezone.localdate().year))
    if nam.isdigit():
        queryset = queryset.filter(tu_ngay__year=int(nam))
    else:
        nam = ""

    selected_loai = "" if loai_hoat_dong is None else str(loai_hoat_dong.pk)
    filters = {}
    if show_filter and selected_phong:
        filters["phong"] = selected_phong
    if nam:
        filters["nam"] = nam
    if selected_loai:
        filters["loai"] = selected_loai
    if trang_thai:
        filters["trang_thai"] = trang_thai
    if ten:
        filters["ten"] = ten
    page_obj = Paginator(queryset, LIST_PAGE_SIZE).get_page(
        request.GET.get("trang")
    )

    return render(
        request,
        "activities/hoat_dong_list.html",
        {
            "activities": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": urlencode(filters),
            "activity_types": _activity_types(departments),
            "statuses": TrangThaiHoatDong.choices,
            "selected_nam": nam,
            "selected_loai": selected_loai,
            "selected_trang_thai": trang_thai,
            "selected_ten": ten,
            "show_filter": show_filter,
            "phong_options": visible,
            "selected_phong": selected_phong,
            "can_create": can(request.user, "edit_entry", request.user.phong_id),
            "year_options": range(timezone.localdate().year - 5, timezone.localdate().year + 2),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def hoat_dong_create(request):
    if not can(request.user, "edit_entry", request.user.phong_id):
        raise PermissionDenied
    if request.method == "POST":
        form = HoatDongForm(request.POST, user=request.user)
        if form.is_valid():
            activity = form.save()
            return redirect("activities:hoat_dong_detail", pk=activity.pk)
    else:
        form = HoatDongForm(user=request.user)
    return _render_detail(request, form, can_edit=True)


@login_required
@require_http_methods(["GET", "POST"])
def hoat_dong_detail(request, pk):
    _require_view(request.user)
    activity = _get_activity(request.user, pk)
    can_edit = can(request.user, "edit_entry", activity.phong.pk)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = HoatDongForm(request.POST, instance=activity, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("activities:hoat_dong_detail", pk=activity.pk)
    else:
        form = HoatDongForm(instance=activity, user=request.user) if can_edit else None
    return _render_detail(request, form, activity=activity, can_edit=can_edit)


@login_required
@require_POST
def hoat_dong_da_to_chuc(request, pk):
    _require_view(request.user)
    activity = _get_activity(request.user, pk)
    if not can(request.user, "edit_entry", activity.phong.pk):
        raise PermissionDenied
    if activity.trang_thai != TrangThaiHoatDong.DA_TO_CHUC:
        activity.trang_thai = TrangThaiHoatDong.DA_TO_CHUC
        activity._change_reason = "Chuyển sang Đã tổ chức"
        try:
            activity.save()
        except ValidationError as exc:
            activity.refresh_from_db()
            form = HoatDongForm(instance=activity, user=request.user)
            return _render_detail(
                request,
                form,
                activity=activity,
                can_edit=True,
                transition_errors=exc.messages,
            )
    return redirect("activities:hoat_dong_detail", pk=activity.pk)


@login_required
@require_POST
def don_vi_them(request):
    if not can(request.user, "edit_entry", request.user.phong_id):
        raise PermissionDenied
    selected_don_vi_ids = []
    for value in request.POST.getlist("don_vi_phoi_hop"):
        if value.isdigit():
            selected_don_vi_ids.append(int(value))
    error = ""
    notice = ""
    name = request.POST.get("ten_don_vi_moi", "").strip()
    if not name:
        error = "Nhập tên đơn vị phối hợp."
    else:
        existing = next(
            (
                row
                for row in DonViPhoiHop.objects.only("pk", "ten_don_vi").order_by("id")
                if row.ten_don_vi.strip().casefold() == name.casefold()
            ),
            None,
        )
        if existing is None:
            existing = DonViPhoiHop(ten_don_vi=name)
            existing.save()
        else:
            notice = "Đơn vị đã có trong danh mục; đã chọn đơn vị hiện có."
        if existing.pk not in selected_don_vi_ids:
            selected_don_vi_ids.append(existing.pk)
    return render(
        request,
        "activities/don_vi_form.html",
        {
            "don_vi_options": DonViPhoiHop.objects.order_by("ten_don_vi", "id"),
            "selected_don_vi_ids": selected_don_vi_ids,
            "don_vi_error": error,
            "don_vi_notice": notice,
        },
    )


def _du_an_queryset(user):
    return scoped(
        user,
        DuAn.objects.select_related("phong"),
        "phong_id",
    )


@login_required
@require_GET
def du_an_list(request):
    _require_view(request.user)
    page_obj = Paginator(
        _du_an_queryset(request.user),
        LIST_PAGE_SIZE,
    ).get_page(request.GET.get("trang"))
    return render(
        request,
        "activities/du_an_list.html",
        {
            "projects": page_obj.object_list,
            "page_obj": page_obj,
            "page_query": "",
            "can_create": can(request.user, "edit_entry", request.user.phong_id),
        },
    )


@login_required
@require_http_methods(["GET", "POST"])
def du_an_create(request):
    if not can(request.user, "edit_entry", request.user.phong_id):
        raise PermissionDenied
    if request.method == "POST":
        form = DuAnForm(request.POST, user=request.user)
        if form.is_valid():
            project = form.save(commit=False)
            if not can(request.user, "edit_entry", project.phong_id):
                raise PermissionDenied
            project.save()
            return redirect("activities:du_an_detail", pk=project.pk)
    else:
        form = DuAnForm(user=request.user)
    return render(
        request,
        "activities/du_an_form.html",
        {"form": form, "project": None, "can_edit": True},
    )


@login_required
@require_http_methods(["GET", "POST"])
def du_an_detail(request, pk):
    _require_view(request.user)
    project = get_object_or_404(_du_an_queryset(request.user), pk=pk)
    can_edit = can(request.user, "edit_entry", project.phong_id)
    if request.method == "POST":
        if not can_edit:
            raise PermissionDenied
        form = DuAnForm(request.POST, instance=project, user=request.user)
        if form.is_valid():
            form.save()
            return redirect("activities:du_an_detail", pk=project.pk)
    else:
        form = DuAnForm(instance=project, user=request.user) if can_edit else None
    return render(
        request,
        "activities/du_an_form.html",
        {"form": form, "project": project, "can_edit": can_edit},
    )
