"""Departments, indicators, annual plans, lookup tables, and form templates."""

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import transaction
from django.shortcuts import redirect, render
from django.views.decorators.http import require_GET, require_http_methods

from apps.accounts.permissions import can
from apps.accounts.roles import Role
from apps.accounts.scoping import scoped
from apps.catalog.forms import TraLaiKeHoachForm
from apps.catalog.models import (
    ChiTieu,
    ChiTieuKeHoach,
    NhomChiTieu,
    PhongBan,
    TrangThaiKeHoach,
)
from apps.reporting.formatting import format_vi_number

_UNSCOPED = frozenset({Role.CENTER_HEAD, Role.SYSTEM_ADMIN})


def _format_plan(value):
    if value is None:
        return "chỉ theo dõi"
    return format_vi_number(value)


def _departments_for(request):
    visible = scoped(request.user, PhongBan.objects.all(), "id").order_by("ma_phong")
    show_filter = request.user.role in _UNSCOPED
    selected = request.GET.get("phong", "") if show_filter else ""
    departments = visible
    if show_filter and selected:
        departments = visible.filter(ma_phong=selected)
    return visible, departments, show_filter, selected


def _catalog_groups(departments):
    phong_ids = list(departments.values_list("pk", flat=True))
    groups = list(
        NhomChiTieu.objects.filter(phong_id__in=phong_ids)
        .select_related("phong")
        .order_by("phong__ma_phong", "thu_tu", "id")
    )
    indicators = list(
        ChiTieu.objects.filter(nhom__phong_id__in=phong_ids, dang_su_dung=True)
        .select_related("nhom", "nhom__phong")
        .order_by("ma_chi_tieu")
    )
    by_id = {row.pk: row for row in indicators}
    children = {}
    roots = {group.pk: [] for group in groups}
    for row in indicators:
        parent = by_id.get(row.chi_tieu_cha_id)
        if parent is not None and parent.nhom_id == row.nhom_id:
            children.setdefault(parent.pk, []).append(row)
        else:
            roots.setdefault(row.nhom_id, []).append(row)

    def walk(row, depth):
        yield row, depth
        for child in children.get(row.pk, []):
            yield from walk(child, depth + 1)

    for group in groups:
        group.nodes = [
            node
            for root in roots.get(group.pk, [])
            for node in walk(root, 0)
        ]
    return groups


def _plan_lines(group, plans, nam):
    lines = []
    for indicator, depth in group.nodes:
        keys = {
            plan.doi_tuong_id
            for plan in plans.get(indicator.pk, [])
            if plan.nam in (nam, nam - 1)
        }
        if not keys:
            keys = {None}
        for doi_tuong_id in sorted(keys, key=lambda value: (value is not None, value or 0)):
            current = _plan_for(plans, indicator.pk, nam, doi_tuong_id)
            previous = _plan_for(plans, indicator.pk, nam - 1, doi_tuong_id)
            label = indicator.ten_chi_tieu
            if current and current.doi_tuong_id:
                label = f"{label} — {current.doi_tuong}"
            elif previous and previous.doi_tuong_id:
                label = f"{label} — {previous.doi_tuong}"
            lines.append(
                {
                    "depth": depth,
                    "ma": indicator.ma_chi_tieu,
                    "label": label,
                    "nam_truoc": _format_plan(
                        None if previous is None else previous.gia_tri_ke_hoach
                    ),
                    "nam_nay": _format_plan(
                        None if current is None else current.gia_tri_ke_hoach
                    ),
                    "trang_thai": (
                        current.get_trang_thai_display() if current is not None else ""
                    ),
                }
            )
    return lines


def _plan_for(plans, chi_tieu_id, nam, doi_tuong_id):
    for plan in plans.get(chi_tieu_id, []):
        if plan.nam == nam and plan.doi_tuong_id == doi_tuong_id:
            return plan
    return None


def _plans_by_indicator(departments, nam):
    phong_ids = list(departments.values_list("pk", flat=True))
    grouped = {}
    rows = ChiTieuKeHoach.objects.filter(
        chi_tieu__nhom__phong_id__in=phong_ids,
        nam__in=(nam, nam - 1),
    ).select_related("doi_tuong", "chi_tieu")
    for plan in rows:
        grouped.setdefault(plan.chi_tieu_id, []).append(plan)
    return grouped


def _copy_previous_plan(phong_id, nam):
    """Copy non-empty plan rows into this year's drafts.

    Returns ``(created, skipped)`` or ``None`` when the previous year has no
    numbers.  Existing draft or confirmed rows are never overwritten.
    """
    previous = list(
        ChiTieuKeHoach.objects.filter(
            nam=nam - 1,
            chi_tieu__nhom__phong_id=phong_id,
            gia_tri_ke_hoach__isnull=False,
        ).select_related("chi_tieu")
    )
    if not previous:
        return None
    existing = set(
        ChiTieuKeHoach.objects.filter(
            nam=nam,
            chi_tieu__nhom__phong_id=phong_id,
        ).values_list("chi_tieu_id", "doi_tuong_id")
    )
    created = 0
    skipped = 0
    for plan in previous:
        key = (plan.chi_tieu_id, plan.doi_tuong_id)
        if key in existing:
            skipped += 1
            continue
        ChiTieuKeHoach.objects.create(
            chi_tieu_id=plan.chi_tieu_id,
            nam=nam,
            doi_tuong_id=plan.doi_tuong_id,
            gia_tri_ke_hoach=plan.gia_tri_ke_hoach,
            trang_thai=TrangThaiKeHoach.DU_THAO,
        )
        existing.add(key)
        created += 1
    return created, skipped


@login_required
@require_http_methods(["GET", "POST"])
def ke_hoach(request, nam):
    if not can(request.user, "view_plan"):
        raise PermissionDenied
    can_confirm = request.user.role == Role.DEPARTMENT_HEAD and can(
        request.user, "confirm_plan", request.user.phong_id
    )
    form = TraLaiKeHoachForm()
    if request.method == "POST":
        if not can_confirm:
            raise PermissionDenied
        plans = ChiTieuKeHoach.objects.filter(
            nam=nam,
            chi_tieu__nhom__phong_id=request.user.phong_id,
        )
        action = request.POST.get("hanh_dong")
        if action == "sao_chep":
            with transaction.atomic():
                result = _copy_previous_plan(request.user.phong_id, nam)
            if result is None:
                messages.warning(
                    request,
                    "Năm trước chưa có số kế hoạch để sao chép.",
                )
            else:
                created, skipped = result
                messages.success(
                    request,
                    f"Đã sao chép {created} dòng, bỏ qua {skipped} dòng đã có.",
                )
            return redirect("catalog:ke_hoach", nam=nam)
        if action == "xac_nhan":
            for plan in plans:
                if plan.trang_thai != TrangThaiKeHoach.DA_XAC_NHAN:
                    plan.trang_thai = TrangThaiKeHoach.DA_XAC_NHAN
                    plan._change_reason = "Xác nhận kế hoạch năm"
                    plan.save()
            return redirect("catalog:ke_hoach", nam=nam)
        if action == "tra_lai":
            form = TraLaiKeHoachForm(request.POST)
            if form.is_valid():
                y_kien = form.cleaned_data["y_kien"].strip()
                for plan in plans:
                    plan.trang_thai = TrangThaiKeHoach.DU_THAO
                    plan.ly_do = y_kien
                    plan._change_reason = y_kien
                    plan.save()
                return redirect("catalog:ke_hoach", nam=nam)
        else:
            raise PermissionDenied

    visible, departments, show_filter, selected = _departments_for(request)
    groups = _catalog_groups(departments)
    plans = _plans_by_indicator(departments, nam)
    for group in groups:
        group.lines = _plan_lines(group, plans, nam)
    return render(
        request,
        "catalog/ke_hoach.html",
        {
            "nam": nam,
            "nam_truoc": nam - 1,
            "nam_sau": nam + 1,
            "groups": groups,
            "show_filter": show_filter,
            "phong_options": visible,
            "selected": selected,
            "can_confirm": can_confirm,
            "can_copy": can_confirm,
            "form": form,
            "read_only_admin": request.user.role == Role.SYSTEM_ADMIN,
        },
    )


@login_required
@require_GET
def danh_muc(request):
    if not can(request.user, "view_catalog"):
        raise PermissionDenied
    _visible, departments, _show_filter, _selected = _departments_for(request)
    groups = _catalog_groups(departments)
    return render(
        request,
        "catalog/danh_muc.html",
        {"groups": groups},
    )
