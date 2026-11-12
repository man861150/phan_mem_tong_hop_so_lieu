"""The single approval and lock workflow for entry phiếu.

Every transition follows the same order: check the actor's permission, lock
the phiếu, validate the current state and comment, apply the change, write the
audit row, and commit.  Views call this module instead of changing
``trang_thai`` directly.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

from django.core.exceptions import PermissionDenied, ValidationError
from django.db import transaction
from django.http import QueryDict
from django.utils import timezone

from apps.accounts.permissions import can
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LichSuXuLy,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)


class WorkflowError(Exception):
    """Base class for expected workflow failures."""


class InvalidTransition(WorkflowError):
    """The requested action is not legal from the phiếu's current state."""


class CommentRequired(WorkflowError):
    """A return or reopen was submitted without a comment."""


@dataclass(frozen=True)
class _Rule:
    from_statuses: tuple[str, ...]
    to_status: str
    permission: str
    comment_required: bool = False


_RULES = {
    HanhDongXuLy.GUI: _Rule(
        (TrangThaiPhieu.NHAP, TrangThaiPhieu.TRA_LAI),
        TrangThaiPhieu.CHO_DUYET,
        "edit_entry",
    ),
    HanhDongXuLy.DUYET: _Rule(
        (TrangThaiPhieu.CHO_DUYET,),
        TrangThaiPhieu.DA_DUYET,
        "approve_entry",
    ),
    HanhDongXuLy.TRA_LAI: _Rule(
        (TrangThaiPhieu.CHO_DUYET,),
        TrangThaiPhieu.TRA_LAI,
        "approve_entry",
        comment_required=True,
    ),
    HanhDongXuLy.MO_LAI: _Rule(
        (TrangThaiPhieu.DA_DUYET,),
        TrangThaiPhieu.NHAP,
        "approve_entry",
        comment_required=True,
    ),
}


def _status_label(value):
    return TrangThaiPhieu(value).label


def _transition(phieu_id, user, action, *, y_kien="", apply=None):
    """Apply one transition and return ``(phiếu, audit row)``.

    The phiếu is locked inside a transaction.  ``apply`` is called only after
    permission, state, and comment checks pass; it is where callers persist
    validated form values so form saving and the status change commit together.
    """
    rule = _RULES.get(action)
    if rule is None:
        raise InvalidTransition("Hành động xử lý phiếu không hợp lệ.")

    try:
        current = PhieuNhapLieu.objects.only(
            "pk", "phong_id", "trang_thai"
        ).get(pk=phieu_id)
    except PhieuNhapLieu.DoesNotExist as exc:
        raise InvalidTransition("Không tìm thấy phiếu nhập liệu.") from exc

    if not can(user, rule.permission, current.phong_id):
        raise PermissionDenied

    comment = (y_kien or "").strip()

    with transaction.atomic():
        phieu = PhieuNhapLieu.objects.select_for_update().get(pk=phieu_id)
        if not can(user, rule.permission, phieu.phong_id):
            raise PermissionDenied
        if phieu.trang_thai not in rule.from_statuses:
            allowed = ", ".join(
                _status_label(status) for status in rule.from_statuses
            )
            raise InvalidTransition(
                "Không thể thực hiện hành động này khi phiếu đang ở trạng "
                f"thái {_status_label(phieu.trang_thai)}. "
                f"Trạng thái hợp lệ: {allowed}."
            )
        if rule.comment_required and not comment:
            raise CommentRequired(
                "Vui lòng nhập ý kiến khi trả lại hoặc mở lại phiếu."
            )

        if apply is not None:
            apply(phieu)

        phieu.trang_thai = rule.to_status
        update_fields = ["trang_thai"]
        if action == HanhDongXuLy.GUI:
            phieu.ngay_gui = timezone.now()
            update_fields.append("ngay_gui")
        phieu._change_reason = _status_label(rule.to_status)
        phieu.save(update_fields=update_fields)

        history = LichSuXuLy.objects.create(
            phieu=phieu,
            nguoi_xu_ly=user,
            hanh_dong=action,
            y_kien=comment,
        )

    return phieu, history


def submit(phieu, user, *, apply=None):
    """Move an editable phiếu to ``cho_duyet``."""
    return _transition(
        phieu.pk,
        user,
        HanhDongXuLy.GUI,
        apply=apply,
    )


def approve(phieu, user):
    """Move a waiting phiếu to ``da_duyet``."""
    return _transition(phieu.pk, user, HanhDongXuLy.DUYET)


def return_phieu(phieu, user, y_kien):
    """Move a waiting phiếu back to ``tra_lai`` with a required comment."""
    return _transition(
        phieu.pk,
        user,
        HanhDongXuLy.TRA_LAI,
        y_kien=y_kien,
    )


def reopen(phieu, user, y_kien):
    """Move an approved phiếu back to ``nhap`` with a required comment."""
    return _transition(
        phieu.pk,
        user,
        HanhDongXuLy.MO_LAI,
        y_kien=y_kien,
    )


def _persisted_form_data(phieu):
    """Build bound form data from the persisted ``SoLieu`` rows."""
    data = QueryDict(mutable=True)
    rows = SoLieu.objects.filter(phieu=phieu).select_related(
        "chi_tieu",
        "doi_tuong",
        "linh_vuc",
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[row.chi_tieu_id].append(row)

    for chi_tieu_id, group in grouped.items():
        total = next(
            (
                row
                for row in group
                if row.doi_tuong_id is None and row.linh_vuc_id is None
            ),
            None,
        )
        if total is not None:
            data[f"gia_tri_{chi_tieu_id}"] = (
                "" if total.gia_tri is None else str(total.gia_tri)
            )
            data[f"nguon_{chi_tieu_id}"] = (
                "" if total.nguon_id is None else str(total.nguon_id)
            )
        else:
            data[f"gia_tri_{chi_tieu_id}"] = ""

        for row in group:
            if row.doi_tuong_id is not None:
                data[f"doi_tuong_{chi_tieu_id}_{row.doi_tuong_id}"] = (
                    "" if row.gia_tri is None else str(row.gia_tri)
                )

        linh_vuc_rows = [
            row for row in group if row.linh_vuc_id is not None
        ]
        if linh_vuc_rows:
            data.setlist(
                f"linh_vuc_{chi_tieu_id}",
                [str(row.linh_vuc_id) for row in linh_vuc_rows],
            )
            data.setlist(
                f"gia_tri_lv_{chi_tieu_id}",
                [
                    "" if row.gia_tri is None else str(row.gia_tri)
                    for row in linh_vuc_rows
                ],
            )
    return data


def _form_errors(form):
    messages = []
    for field_name, field_errors in form.errors.items():
        field = form.fields.get(field_name)
        label = field.label if field is not None and field.label else ""
        for message in field_errors:
            messages.append(f"{label}: {message}" if label else str(message))
    return messages


def _submission_form(phieu):
    """Return ``(form, blockers)`` for the phiếu's persisted values."""
    from apps.entry.forms import ActivityEntryForm, MonthlyEntryForm

    data = _persisted_form_data(phieu)
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG:
        activity = phieu.hoat_dong
        if activity is None:
            return None, ["Phiếu chưa có hoạt động."]
        if activity.la_nhiem_vu_phat_sinh:
            blockers = []
            if not (activity.noi_dung or "").strip():
                blockers.append("Chưa nhập nội dung nhiệm vụ phát sinh.")
            if not (activity.ket_qua or "").strip():
                blockers.append("Chưa nhập kết quả nhiệm vụ phát sinh.")
            return None, blockers
        return (
            ActivityEntryForm(
                data=data,
                activity=activity,
                phieu=phieu,
            ),
            [],
        )
    if phieu.loai_phieu == LoaiPhieu.THANG:
        if phieu.ky is None:
            return None, ["Phiếu tháng chưa có kỳ báo cáo."]
        return (
            MonthlyEntryForm(
                data=data,
                phong=phieu.phong,
                ky=phieu.ky,
                phieu=phieu,
            ),
            [],
        )
    if phieu.loai_phieu == LoaiPhieu.DU_AN:
        if not HoTroDuAn.objects.filter(phieu=phieu).exists():
            return None, ["Chưa có dòng hỗ trợ dự án."]
        return None, []
    return None, []


def submission_errors(phieu):
    """Return Vietnamese blockers for submit and bulk approval.

    The check rebuilds the persisted values into the same form used by the
    entry screen, so split mismatches and missing required rows are detected
    exactly as they would be on a normal submit.
    """
    form, blockers = _submission_form(phieu)
    if blockers:
        return blockers
    if form is None:
        return []
    if not form.is_valid():
        return _form_errors(form)
    try:
        form.validate_required()
    except ValidationError as exc:
        return exc.messages
    return []


def changes_since_previous_submit(phieu):
    """Return value changes made since the relevant earlier submission.

    A returned phiếu is compared with the send that preceded the return.  A
    resubmitted waiting phiếu is compared with the send before the latest one;
    otherwise the comparison starts at the latest send.
    """
    sends = list(
        phieu.lich_su_xu_ly.filter(hanh_dong=HanhDongXuLy.GUI).order_by(
            "thoi_diem",
            "id",
        )
    )
    if not sends:
        return []
    if phieu.trang_thai == TrangThaiPhieu.CHO_DUYET and len(sends) > 1:
        cutoff = sends[-2].thoi_diem
    else:
        cutoff = sends[-1].thoi_diem

    snapshots = (
        SoLieu.history.filter(phieu_id=phieu.pk)
        .select_related("chi_tieu", "doi_tuong", "linh_vuc")
        .order_by("history_date", "history_id")
    )
    previous = {}
    changes = []
    for snapshot in snapshots.iterator():
        old_snapshot = previous.get(snapshot.id)
        if snapshot.history_date > cutoff:
            old_value = old_snapshot.gia_tri if old_snapshot else None
            new_value = (
                snapshot.gia_tri if snapshot.history_type != "-" else None
            )
            if old_value != new_value:
                suffix = []
                if snapshot.doi_tuong_id:
                    suffix.append(snapshot.doi_tuong.ten_doi_tuong)
                if snapshot.linh_vuc_id:
                    suffix.append(
                        f"{snapshot.linh_vuc.get_he_thong_display()} — "
                        f"{snapshot.linh_vuc.ten}"
                    )
                label = snapshot.chi_tieu.ten_chi_tieu
                if suffix:
                    label = f"{label} ({' / '.join(suffix)})"
                changes.append(
                    {
                        "label": label,
                        "old": old_value,
                        "new": new_value,
                        "nguoi": snapshot.history_user,
                        "thoi_diem": snapshot.history_date,
                    }
                )
        previous[snapshot.id] = snapshot
    return changes
