"""Read-only work queues for the guided workflow page.

The guide links to screens that already exist. It does not create a phiếu,
change a status, or submit anything.
"""

from django.db.models import Q
from django.urls import reverse

from apps.accounts.permissions import can
from apps.accounts.scoping import scoped
from apps.activities.models import DuAn, HoatDong, TrangThaiHoatDong
from apps.catalog.models import KyBaoCao, TrangThaiKy
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LichSuXuLy,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)
from apps.entry.workflow import PERIOD_CLOSED_MESSAGE

ROW_LIMIT = 20

COMPLETED = "completed"
CURRENT = "current"
UPCOMING = "upcoming"
BLOCKED = "blocked"

STEP_STATE_LABELS = {
    COMPLETED: "Hoàn thành",
    CURRENT: "Đang làm",
    UPCOMING: "Chưa tới",
    BLOCKED: "Cần xử lý",
}
PILL_LABELS = {
    COMPLETED: "Hoàn thành",
    CURRENT: "Đang làm",
    UPCOMING: "Chưa tới",
    BLOCKED: "Không thể thực hiện",
}

_ACTIONABLE = (
    TrangThaiPhieu.NHAP,
    TrangThaiPhieu.TRA_LAI,
    TrangThaiPhieu.CHO_DUYET,
)
_RANK_RETURNED = 0
_RANK_DRAFT_EMPTY = 1
_RANK_DRAFT_FILLED = 2
_RANK_PREREQ = 3
_RANK_WAITING = 4

_WAITING_OFFICER = (
    "Phiếu đang chờ lãnh đạo phòng duyệt. Bạn chỉ được xem."
)
_WAITING_HEAD = "Phiếu đang chờ duyệt. Mở chi tiết để duyệt hoặc trả lại."
_NO_PERIODS = (
    "Chưa có kỳ báo cáo. Quản trị hệ thống mở kỳ trong trang quản trị."
)
_NO_OPEN_PERIOD = "Không có kỳ đang mở. Kỳ đã đóng chỉ được xem."
_CLOSED_HEAD = (
    "Kỳ đã đóng nên không lưu hoặc gửi thêm. Bạn vẫn có thể duyệt "
    "phiếu đang chờ."
)

_ACTIVITY_STEPS = (
    "Tạo hoạt động",
    "Chuyển sang Đã tổ chức",
    "Mở phiếu kết quả",
    "Nhập số liệu và lưu nháp",
    "Gửi duyệt",
    "Xem trạng thái hoặc sửa nếu bị trả lại",
)
_MONTH_STEPS = (
    "Chọn kỳ đang mở",
    "Nhập số liệu",
    "Lưu nháp",
    "Gửi duyệt",
    "Xem trạng thái hoặc sửa nếu bị trả lại",
)
_PROJECT_STEPS = (
    "Chọn hoặc tạo dự án",
    "Ghi nhận hỗ trợ",
    "Lưu nháp",
    "Gửi duyệt",
    "Xem trạng thái hoặc sửa nếu bị trả lại",
)


def build_guide(user):
    """Return the three workflows and the approval card for this user."""
    can_edit = can(user, "edit_entry")
    can_approve = can(user, "approve_entry")
    context = {
        "workflows": [
            _activity_workflow(user, can_edit, can_approve),
            _month_workflow(user, can_edit, can_approve),
            _project_workflow(user, can_edit, can_approve),
        ],
        "summary": _phieu_summary(user),
        "approval": None,
    }
    if can_approve:
        context["approval"] = {
            "count": _phieu_queryset(user)
            .filter(trang_thai=TrangThaiPhieu.CHO_DUYET)
            .count(),
            "url": reverse("entry:duyet_list"),
        }
    return context


def _phieu_summary(user):
    """Count the scoped phiếu that sit in each header counter."""
    queryset = _phieu_queryset(user)
    return {
        "in_progress": queryset.filter(
            trang_thai__in=(TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI)
        ).count(),
        "pending": queryset.filter(
            trang_thai=TrangThaiPhieu.CHO_DUYET
        ).count(),
        "completed": queryset.filter(
            trang_thai=TrangThaiPhieu.DA_DUYET,
            la_phieu_bo_sung=False,
        ).count(),
    }


def _activity_workflow(user, can_edit, can_approve):
    activities = scoped(
        user,
        HoatDong.objects.select_related(
            "loai_hoat_dong",
            "loai_hoat_dong__phong",
        ),
        "loai_hoat_dong__phong_id",
    )
    phieu_rows = list(
        _phieu_queryset(user)
        .filter(loai_phieu=LoaiPhieu.HOAT_DONG)
        .select_related(
            "hoat_dong",
            "hoat_dong__loai_hoat_dong",
            "hoat_dong__loai_hoat_dong__phong",
        )
    )
    primary_ids = {
        phieu.hoat_dong_id
        for phieu in phieu_rows
        if not phieu.la_phieu_bo_sung and phieu.hoat_dong_id
    }
    setup = list(
        activities.filter(
            Q(trang_thai=TrangThaiHoatDong.KE_HOACH)
            | Q(trang_thai=TrangThaiHoatDong.DA_TO_CHUC)
        ).exclude(pk__in=primary_ids)
    )
    valued = _valued_phieu_ids([phieu.pk for phieu in phieu_rows])
    comments = _return_comments(
        [
            phieu.pk
            for phieu in phieu_rows
            if phieu.trang_thai == TrangThaiPhieu.TRA_LAI
        ]
    )
    items = []
    seen_setup = set()
    for activity in setup:
        if activity.trang_thai != TrangThaiHoatDong.DA_TO_CHUC:
            items.append(
                _planned_activity_item(activity, can_edit=can_edit)
            )
            seen_setup.add(activity.pk)
            continue
        items.append(
            _missing_phieu_item(
                activity,
                can_edit=can_edit,
            )
        )
        seen_setup.add(activity.pk)

    for phieu in phieu_rows:
        activity = phieu.hoat_dong
        if activity is None or phieu.trang_thai not in _ACTIONABLE:
            continue
        if (
            not phieu.la_phieu_bo_sung
            and activity.trang_thai != TrangThaiHoatDong.DA_TO_CHUC
        ):
            if activity.pk not in seen_setup:
                items.append(
                    _planned_activity_item(activity, can_edit=can_edit)
                )
                seen_setup.add(activity.pk)
            continue
        items.append(
            _activity_phieu_item(
                activity,
                phieu,
                can_edit=can_edit,
                can_approve=can_approve,
                has_content=_activity_has_content(activity, phieu, valued),
                comment=comments.get(phieu.pk, ""),
            )
        )

    completed = (
        _phieu_queryset(user)
        .filter(
            loai_phieu=LoaiPhieu.HOAT_DONG,
            la_phieu_bo_sung=False,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        .count()
    )
    create_url = reverse("activities:hoat_dong_create") if can_edit else ""
    if items:
        focus_number, blocked = _focus(items)
        empty_message = ""
        primary = ("", "", "")
    elif completed:
        focus_number, blocked = None, False
        empty_message = "Không còn hoạt động cần xử lý."
        primary = (create_url, "Tạo hoạt động", "")
    else:
        focus_number, blocked = 1, not can_edit
        empty_message = "Chưa có hoạt động trong phòng."
        primary = (create_url, "Tạo hoạt động", "")
    return _workflow(
        key="hoat_dong",
        eyebrow="Hoạt động",
        title="Kết quả hoạt động",
        explanation=(
            "Tạo hoạt động, chuyển sang Đã tổ chức, rồi nhập phiếu kết quả "
            "và gửi duyệt."
        ),
        step_titles=_ACTIVITY_STEPS,
        items=items,
        focus_number=focus_number,
        focus_blocked=blocked,
        more_url=reverse("activities:hoat_dong_list"),
        more_label="Xem danh sách hoạt động",
        completed_count=completed,
        completed_url=reverse("activities:hoat_dong_list"),
        completed_label="Xem danh sách hoạt động",
        primary=primary,
        empty_message=empty_message,
        blocked_message="",
    )


def _month_workflow(user, can_edit, can_approve):
    periods = list(KyBaoCao.objects.order_by("-nam", "-so_ky", "-id"))
    phieu_rows = list(
        _phieu_queryset(user)
        .filter(loai_phieu=LoaiPhieu.THANG)
        .select_related("ky")
    )
    primary_by_ky = {
        phieu.ky_id: phieu
        for phieu in phieu_rows
        if not phieu.la_phieu_bo_sung and phieu.ky_id
    }
    valued = _valued_phieu_ids([phieu.pk for phieu in phieu_rows])
    comments = _return_comments(
        [
            phieu.pk
            for phieu in phieu_rows
            if phieu.trang_thai == TrangThaiPhieu.TRA_LAI
        ]
    )
    items = []
    completed = 0
    open_ids = set()
    for ky in periods:
        if ky.trang_thai == TrangThaiKy.MO:
            open_ids.add(ky.pk)
        phieu = primary_by_ky.get(ky.pk)
        if phieu is not None and phieu.trang_thai == TrangThaiPhieu.DA_DUYET:
            completed += 1
            continue
        if phieu is None:
            if ky.trang_thai == TrangThaiKy.MO:
                items.append(_open_month_item(ky, can_edit=can_edit))
            continue
        items.append(
            _month_phieu_item(
                ky,
                phieu,
                can_edit=can_edit,
                can_approve=can_approve,
                has_content=phieu.pk in valued,
                comment=comments.get(phieu.pk, ""),
            )
        )
    for phieu in phieu_rows:
        if not phieu.la_phieu_bo_sung or phieu.trang_thai not in _ACTIONABLE:
            continue
        if phieu.ky is None:
            continue
        items.append(
            _month_phieu_item(
                phieu.ky,
                phieu,
                can_edit=can_edit,
                can_approve=can_approve,
                has_content=phieu.pk in valued,
                comment=comments.get(phieu.pk, ""),
                supplement=True,
            )
        )

    chooser = reverse("entry:phieu_thang_chon")
    blocked_message = ""
    if not periods:
        focus_number, blocked = 1, True
        blocked_message = _NO_PERIODS
        empty_message = ""
        primary = ("", "", "")
    elif not items and not open_ids:
        focus_number, blocked = 1, True
        blocked_message = _NO_OPEN_PERIOD
        empty_message = ""
        primary = (chooser, "Xem các kỳ báo cáo", "")
    elif not items:
        focus_number, blocked = None, False
        empty_message = "Kỳ đang mở đã có phiếu đã duyệt."
        primary = (chooser, "Xem các kỳ báo cáo", "")
    else:
        focus_number, blocked = _focus(items)
        empty_message = ""
        primary = ("", "", "")
    return _workflow(
        key="thang",
        eyebrow="Báo cáo định kỳ",
        title="Phiếu tháng",
        explanation=(
            "Chọn kỳ đang mở, nhập số liệu tháng, lưu nháp, rồi gửi duyệt."
        ),
        step_titles=_MONTH_STEPS,
        items=items,
        focus_number=focus_number,
        focus_blocked=blocked,
        more_url=chooser,
        more_label="Xem các kỳ báo cáo",
        completed_count=completed,
        completed_url=chooser,
        completed_label="Xem các kỳ báo cáo",
        primary=primary,
        empty_message=empty_message,
        blocked_message=blocked_message,
    )


def _project_workflow(user, can_edit, can_approve):
    projects = scoped(
        user,
        DuAn.objects.select_related("phong"),
        "phong_id",
    )
    phieu_rows = list(
        _phieu_queryset(user)
        .filter(loai_phieu=LoaiPhieu.DU_AN)
        .select_related("du_an", "du_an__phong")
    )
    primary_ids = {
        phieu.du_an_id
        for phieu in phieu_rows
        if not phieu.la_phieu_bo_sung and phieu.du_an_id
    }
    line_ids = set(
        HoTroDuAn.objects.filter(
            phieu_id__in=[phieu.pk for phieu in phieu_rows]
        )
        .values_list("phieu_id", flat=True)
        .distinct()
    )
    comments = _return_comments(
        [
            phieu.pk
            for phieu in phieu_rows
            if phieu.trang_thai == TrangThaiPhieu.TRA_LAI
        ]
    )
    items = [
        _project_without_phieu_item(project, can_edit=can_edit)
        for project in projects.exclude(pk__in=primary_ids)
    ]
    completed = 0
    for phieu in phieu_rows:
        project = phieu.du_an
        if project is None:
            continue
        if phieu.trang_thai == TrangThaiPhieu.DA_DUYET and not phieu.la_phieu_bo_sung:
            completed += 1
            continue
        if phieu.trang_thai not in _ACTIONABLE:
            continue
        items.append(
            _project_phieu_item(
                project,
                phieu,
                can_edit=can_edit,
                can_approve=can_approve,
                has_lines=phieu.pk in line_ids,
                comment=comments.get(phieu.pk, ""),
            )
        )

    create_url = reverse("activities:du_an_create") if can_edit else ""
    list_url = reverse("activities:du_an_list")
    if items:
        focus_number, blocked = _focus(items)
        empty_message = ""
        primary = ("", "", "")
    elif completed:
        focus_number, blocked = None, False
        empty_message = "Không còn phiếu dự án cần xử lý."
        primary = (create_url, "Thêm dự án", "")
    else:
        focus_number, blocked = 1, not can_edit
        empty_message = "Chưa có dự án trong phòng."
        primary = (create_url, "Thêm dự án", "")
    return _workflow(
        key="du_an",
        eyebrow="Dự án",
        title="Hỗ trợ dự án",
        explanation=(
            "Chọn hoặc tạo dự án, ghi các dòng hỗ trợ, rồi gửi phiếu duyệt."
        ),
        step_titles=_PROJECT_STEPS,
        items=items,
        focus_number=focus_number,
        focus_blocked=blocked,
        more_url=list_url,
        more_label="Xem danh sách dự án",
        completed_count=completed,
        completed_url=list_url,
        completed_label="Xem danh sách dự án",
        primary=primary,
        empty_message=empty_message,
        blocked_message="",
    )


def _planned_activity_item(activity, *, can_edit):
    explanation = (
        "Mở hoạt động và bấm Chuyển sang Đã tổ chức khi hoạt động đã diễn ra."
    )
    if activity.la_nhiem_vu_phat_sinh:
        explanation += (
            " Nhiệm vụ phát sinh cần có nội dung và kết quả trước khi chuyển."
        )
    if can_edit:
        return _item(
            title=activity.ten,
            meta=activity.get_trang_thai_display(),
            step_number=2,
            step_titles=_ACTIVITY_STEPS,
            state=CURRENT,
            explanation=explanation,
            action_url=reverse(
                "activities:hoat_dong_detail",
                args=[activity.pk],
            ),
            action_label="Mở hoạt động để chuyển trạng thái",
            rank=_RANK_PREREQ,
            tie=activity.pk,
        )
    return _item(
        title=activity.ten,
        meta=activity.get_trang_thai_display(),
        step_number=2,
        step_titles=_ACTIVITY_STEPS,
        state=BLOCKED,
        explanation="Bạn không có quyền sửa hoạt động này.",
        action_url=reverse("activities:hoat_dong_detail", args=[activity.pk]),
        action_label="Xem hoạt động",
        rank=_RANK_PREREQ,
        tie=activity.pk,
    )


def _missing_phieu_item(activity, *, can_edit):
    explanation = "Chỉ hoạt động đã tổ chức mới mở được phiếu kết quả."
    if can_edit:
        return _item(
            title=activity.ten,
            meta="Đã tổ chức · Chưa có phiếu",
            step_number=3,
            step_titles=_ACTIVITY_STEPS,
            state=CURRENT,
            explanation=explanation,
            action_url=reverse("entry:phieu_hoat_dong", args=[activity.pk]),
            action_label="Mở phiếu kết quả",
            rank=_RANK_PREREQ,
            tie=activity.pk,
        )
    return _item(
        title=activity.ten,
        meta="Đã tổ chức · Chưa có phiếu",
        step_number=3,
        step_titles=_ACTIVITY_STEPS,
        state=BLOCKED,
        explanation="Bạn không có quyền nhập phiếu kết quả.",
        action_url=reverse("activities:hoat_dong_detail", args=[activity.pk]),
        action_label="Xem hoạt động",
        rank=_RANK_PREREQ,
        tie=activity.pk,
    )


def _activity_phieu_item(
    activity,
    phieu,
    *,
    can_edit,
    can_approve,
    has_content,
    comment,
):
    form_url = reverse("entry:phieu_hoat_dong", args=[activity.pk])
    if phieu.la_phieu_bo_sung:
        form_url = f"{form_url}?phieu={phieu.pk}"
    detail_url = reverse("entry:phieu_detail", args=[phieu.pk])
    meta = phieu.get_trang_thai_display()
    if phieu.la_phieu_bo_sung:
        meta = f"{meta} · Phiếu bổ sung"
    return _phieu_progress_item(
        title=activity.ten,
        meta=meta,
        step_titles=_ACTIVITY_STEPS,
        draft_step=4,
        submit_step=5,
        review_step=6,
        form_url=form_url,
        detail_url=detail_url,
        phieu=phieu,
        can_edit=can_edit,
        can_approve=can_approve,
        has_content=has_content,
        comment=comment,
        period_open=True,
        draft_explanation=(
            "Nhập số liệu trên phiếu, rồi bấm Lưu nháp. Lưu nháp chưa "
            "kiểm tra chỉ tiêu bắt buộc."
        ),
        submit_explanation=(
            "Mở phiếu và bấm Gửi duyệt. Trang phiếu kiểm tra các chỉ tiêu "
            "bắt buộc trước khi gửi."
        ),
        return_explanation=(
            "Sửa theo ý kiến trả lại, rồi gửi duyệt lại trên phiếu."
        ),
        tie=phieu.pk,
    )


def _open_month_item(ky, *, can_edit):
    url = reverse("entry:phieu_thang", args=[ky.pk])
    if can_edit:
        return _item(
            title=_month_title(ky),
            meta="Kỳ đang mở · Chưa có phiếu",
            step_number=2,
            step_titles=_MONTH_STEPS,
            state=CURRENT,
            explanation=(
                "Mở phiếu tháng, nhập số liệu, rồi bấm Lưu nháp trên trang đó."
            ),
            action_url=url,
            action_label="Nhập số liệu và lưu nháp",
            rank=_RANK_DRAFT_EMPTY,
            tie=ky.pk,
            sort_title=f"{ky.nam:04d}-{ky.so_ky:02d}",
        )
    return _item(
        title=_month_title(ky),
        meta="Kỳ đang mở · Chưa có phiếu",
        step_number=2,
        step_titles=_MONTH_STEPS,
        state=BLOCKED,
        explanation="Bạn không có quyền nhập phiếu tháng.",
        action_url=url,
        action_label="Xem phiếu",
        rank=_RANK_DRAFT_EMPTY,
        tie=ky.pk,
        sort_title=f"{ky.nam:04d}-{ky.so_ky:02d}",
    )


def _month_phieu_item(
    ky,
    phieu,
    *,
    can_edit,
    can_approve,
    has_content,
    comment,
    supplement=False,
):
    period_open = ky.trang_thai == TrangThaiKy.MO
    meta = phieu.get_trang_thai_display()
    if not period_open:
        meta = f"{meta} · Kỳ đã đóng"
    if supplement:
        meta = f"{meta} · Phiếu bổ sung"
    form_url = reverse("entry:phieu_thang", args=[ky.pk])
    detail_url = reverse("entry:phieu_detail", args=[phieu.pk])
    return _phieu_progress_item(
        title=_month_title(ky),
        meta=meta,
        step_titles=_MONTH_STEPS,
        draft_step=2,
        submit_step=4,
        review_step=5,
        form_url=form_url,
        detail_url=detail_url,
        phieu=phieu,
        can_edit=can_edit,
        can_approve=can_approve,
        has_content=has_content,
        comment=comment,
        period_open=period_open,
        draft_explanation=(
            "Mở phiếu tháng, nhập số liệu, rồi bấm Lưu nháp trên trang đó."
        ),
        submit_explanation=(
            "Mở phiếu tháng và bấm Gửi duyệt. Trang phiếu kiểm tra các "
            "chỉ tiêu bắt buộc."
        ),
        return_explanation=(
            "Sửa theo ý kiến trả lại, rồi gửi duyệt lại trên phiếu tháng."
        ),
        tie=phieu.pk,
        sort_title=f"{ky.nam:04d}-{ky.so_ky:02d}-{phieu.pk}",
        view_url=form_url,
        view_label="Xem phiếu",
    )


def _project_without_phieu_item(project, *, can_edit):
    if can_edit:
        return _item(
            title=project.ten_du_an,
            meta=f"Năm {project.nam} · Chưa có phiếu",
            step_number=2,
            step_titles=_PROJECT_STEPS,
            state=CURRENT,
            explanation=(
                "Mở phiếu hỗ trợ và thêm từng dòng. Mỗi dòng được lưu ngay "
                "trên phiếu."
            ),
            action_url=reverse("entry:phieu_du_an", args=[project.pk]),
            action_label="Mở phiếu hỗ trợ",
            rank=_RANK_PREREQ,
            tie=project.pk,
        )
    return _item(
        title=project.ten_du_an,
        meta=f"Năm {project.nam} · Chưa có phiếu",
        step_number=2,
        step_titles=_PROJECT_STEPS,
        state=BLOCKED,
        explanation="Bạn không có quyền nhập hỗ trợ dự án.",
        action_url=reverse("activities:du_an_detail", args=[project.pk]),
        action_label="Xem dự án",
        rank=_RANK_PREREQ,
        tie=project.pk,
    )


def _project_phieu_item(
    project,
    phieu,
    *,
    can_edit,
    can_approve,
    has_lines,
    comment,
):
    meta = phieu.get_trang_thai_display()
    if phieu.la_phieu_bo_sung:
        meta = f"{meta} · Phiếu bổ sung"
    form_url = reverse("entry:phieu_du_an", args=[project.pk])
    detail_url = reverse("entry:phieu_detail", args=[phieu.pk])
    # The project screen always opens the primary phiếu.
    edit_url = detail_url if phieu.la_phieu_bo_sung else form_url
    return _phieu_progress_item(
        title=project.ten_du_an,
        meta=meta,
        step_titles=_PROJECT_STEPS,
        draft_step=2,
        submit_step=4,
        review_step=5,
        form_url=edit_url,
        detail_url=detail_url,
        phieu=phieu,
        can_edit=can_edit,
        can_approve=can_approve,
        has_content=has_lines,
        comment=comment,
        period_open=True,
        draft_explanation=(
            "Mở phiếu hỗ trợ và thêm từng dòng. Mỗi dòng được lưu ngay "
            "trên phiếu."
        ),
        submit_explanation=(
            "Phiếu đã có dòng hỗ trợ. Mở phiếu và bấm Gửi duyệt. Cần ít "
            "nhất một dòng mới gửi được."
        ),
        return_explanation=(
            "Sửa dòng hỗ trợ theo ý kiến trả lại, rồi gửi duyệt lại."
        ),
        tie=phieu.pk,
    )


def _phieu_progress_item(
    *,
    title,
    meta,
    step_titles,
    draft_step,
    submit_step,
    review_step,
    form_url,
    detail_url,
    phieu,
    can_edit,
    can_approve,
    has_content,
    comment,
    period_open,
    draft_explanation,
    submit_explanation,
    return_explanation,
    tie,
    sort_title="",
    view_url="",
    view_label="Xem phiếu",
):
    status = phieu.trang_thai
    editable = can_edit and period_open and status in (
        TrangThaiPhieu.NHAP,
        TrangThaiPhieu.TRA_LAI,
    )
    if status == TrangThaiPhieu.TRA_LAI:
        explanation = return_explanation
        if not period_open:
            explanation = PERIOD_CLOSED_MESSAGE
        elif not can_edit:
            explanation = "Bạn không có quyền sửa phiếu này."
        return _item(
            title=title,
            meta=meta,
            step_number=review_step,
            step_titles=step_titles,
            state=CURRENT if editable else BLOCKED,
            explanation=explanation,
            action_url=form_url if editable else (view_url or detail_url),
            action_label="Sửa và gửi lại" if editable else view_label,
            comment=comment,
            rank=_RANK_RETURNED,
            tie=tie,
            sort_title=sort_title,
        )
    if status == TrangThaiPhieu.NHAP and not has_content:
        explanation = draft_explanation
        if not period_open:
            explanation = PERIOD_CLOSED_MESSAGE
        elif not can_edit:
            explanation = "Bạn không có quyền sửa phiếu này."
        return _item(
            title=title,
            meta=meta,
            step_number=draft_step,
            step_titles=step_titles,
            state=CURRENT if editable else BLOCKED,
            explanation=explanation,
            action_url=form_url if editable else (view_url or detail_url),
            action_label=(
                "Nhập số liệu và lưu nháp" if editable else view_label
            ),
            rank=_RANK_DRAFT_EMPTY,
            tie=tie,
            sort_title=sort_title,
        )
    if status == TrangThaiPhieu.NHAP:
        explanation = submit_explanation
        if not period_open:
            explanation = PERIOD_CLOSED_MESSAGE
        elif not can_edit:
            explanation = "Bạn không có quyền sửa phiếu này."
        return _item(
            title=title,
            meta=meta,
            step_number=submit_step,
            step_titles=step_titles,
            state=CURRENT if editable else BLOCKED,
            explanation=explanation,
            action_url=form_url if editable else (view_url or detail_url),
            action_label="Mở phiếu để gửi duyệt" if editable else view_label,
            rank=_RANK_DRAFT_FILLED,
            tie=tie,
            sort_title=sort_title,
        )
    if can_approve and status == TrangThaiPhieu.CHO_DUYET:
        explanation = _WAITING_HEAD
        if not period_open:
            explanation = _CLOSED_HEAD
        return _item(
            title=title,
            meta=meta,
            step_number=review_step,
            step_titles=step_titles,
            state=CURRENT,
            explanation=explanation,
            action_url=detail_url,
            action_label="Xem và duyệt",
            rank=_RANK_WAITING,
            tie=tie,
            sort_title=sort_title,
            waiting=True,
        )
    return _item(
        title=title,
        meta=meta,
        step_number=review_step,
        step_titles=step_titles,
        state=BLOCKED,
        explanation=_WAITING_OFFICER,
        action_url=detail_url,
        action_label="Xem trạng thái",
        rank=_RANK_WAITING,
        tie=tie,
        sort_title=sort_title,
        waiting=True,
    )


def _item(
    *,
    title,
    meta,
    step_number,
    step_titles,
    state,
    explanation,
    action_url,
    action_label,
    rank,
    tie,
    comment="",
    sort_title="",
    waiting=False,
):
    return {
        "title": title,
        "meta": meta,
        "step_number": step_number,
        "step_label": f"Bước {step_number} — {step_titles[step_number - 1]}",
        "state": state,
        "state_label": PILL_LABELS[state],
        "state_pill_label": PILL_LABELS[state],
        "explanation": explanation,
        "action_url": action_url,
        "action_label": action_label,
        "comment": comment,
        "rank": rank,
        "tie": tie,
        "sort_title": sort_title or title.casefold(),
        "waiting": waiting,
    }


def _workflow(
    *,
    key,
    eyebrow,
    title,
    explanation,
    step_titles,
    items,
    focus_number,
    focus_blocked,
    more_url,
    more_label,
    completed_count,
    completed_url,
    completed_label,
    primary,
    empty_message,
    blocked_message,
):
    ordered = sorted(
        items,
        key=lambda item: (item["rank"], item["sort_title"], item["tie"]),
    )
    hidden_count = max(0, len(ordered) - ROW_LIMIT)
    visible = [_public_item(item) for item in ordered[:ROW_LIMIT]]
    primary_url, primary_label, primary_hint = primary
    if ordered and not primary_hint:
        primary_url = ordered[0]["action_url"]
        primary_label = ordered[0]["action_label"]
        primary_hint = f"Việc cần làm trước: {ordered[0]['title']}."
    if ordered:
        primary_title = ordered[0]["title"]
    elif focus_number is not None:
        primary_title = step_titles[focus_number - 1]
    else:
        primary_title = "Chưa có việc cần xử lý."
    steps = _steps(step_titles, focus_number, focus_blocked)
    step_badge = (
        f"Bước {focus_number}/{len(steps)}"
        if focus_number is not None
        else "Hoàn thành"
    )
    status_badge = ""
    if focus_number is not None:
        at_focus = [
            item for item in ordered if item["step_number"] == focus_number
        ]
        if (
            key == "du_an"
            and at_focus
            and all(
                item["waiting"] and item["state"] == BLOCKED
                for item in at_focus
            )
        ):
            status_badge = "Chờ phản hồi"
    focus_caption = ""
    if focus_number is not None:
        focus_title = step_titles[focus_number - 1]
        if focus_blocked:
            focus_caption = f"Bước {focus_number} đang tạm dừng: {focus_title}."
        else:
            focus_caption = f"Bước sớm nhất còn dở: {focus_title}."
    return {
        "key": key,
        "eyebrow": eyebrow,
        "title": title,
        "explanation": explanation,
        "steps": steps,
        "step_badge": step_badge,
        "status_badge": status_badge,
        "items": visible,
        "hidden_count": hidden_count,
        "more_url": more_url,
        "more_label": more_label,
        "completed_count": completed_count,
        "completed_url": completed_url,
        "completed_label": completed_label,
        "primary_url": primary_url,
        "primary_label": primary_label,
        "primary_hint": primary_hint,
        "primary_title": primary_title,
        "empty_message": empty_message,
        "blocked_message": blocked_message,
        "focus_caption": focus_caption,
    }


def _steps(titles, focus_number, focus_blocked):
    steps = []
    for number, title in enumerate(titles, start=1):
        if focus_number is None:
            state = COMPLETED
            current = False
        elif number < focus_number:
            state = COMPLETED
            current = False
        elif number == focus_number:
            state = BLOCKED if focus_blocked else CURRENT
            current = True
        else:
            state = UPCOMING
            current = False
        steps.append(
            {
                "number": number,
                "title": title,
                "state": state,
                "state_label": STEP_STATE_LABELS[state],
                "current": current,
            }
        )
    return steps


def _focus(items):
    earliest = min(item["step_number"] for item in items)
    at_step = [item for item in items if item["step_number"] == earliest]
    blocked = all(item["state"] == BLOCKED for item in at_step)
    return earliest, blocked


def _public_item(item):
    return {
        key: value
        for key, value in item.items()
        if key not in {"rank", "tie", "sort_title"}
    }


def _phieu_queryset(user):
    return scoped(user, PhieuNhapLieu.objects.all(), "phong_id")


def _valued_phieu_ids(phieu_ids):
    if not phieu_ids:
        return set()
    return set(
        SoLieu.objects.filter(phieu_id__in=phieu_ids)
        .values_list("phieu_id", flat=True)
        .distinct()
    )


def _return_comments(phieu_ids):
    if not phieu_ids:
        return {}
    comments = {}
    rows = (
        LichSuXuLy.objects.filter(
            phieu_id__in=phieu_ids,
            hanh_dong=HanhDongXuLy.TRA_LAI,
        )
        .order_by("phieu_id", "-thoi_diem", "-id")
        .values_list("phieu_id", "y_kien")
    )
    for phieu_id, comment in rows:
        comments.setdefault(phieu_id, comment)
    return comments


def _activity_has_content(activity, phieu, valued_ids):
    if activity.la_nhiem_vu_phat_sinh:
        return bool(
            (activity.noi_dung or "").strip()
            and (activity.ket_qua or "").strip()
        )
    return phieu.pk in valued_ids


def _month_title(ky):
    return f"Tháng {ky.so_ky}/{ky.nam}"
