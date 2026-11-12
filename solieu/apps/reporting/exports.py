"""File names and immutable snapshot records for report downloads."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from uuid import uuid4

from django.core.files.base import ContentFile
from django.db import transaction
from django.utils import timezone

from apps.reporting.models import (
    BaoCaoDaXuat,
    BaoCaoDaXuatDong,
    DinhDangXuat,
)
from apps.reporting.periods import period_slug
from apps.reporting.report_data import (
    GAP_NOTE,
    DepartmentReport,
    breakdown_label,
)
from apps.reporting.rollup import ReportPeriod


def export_filename(
    period: ReportPeriod,
    phong,
    dinh_dang: str,
    *,
    now: datetime | None = None,
) -> str:
    """Return an ASCII-safe, unique file name.

    The Vietnamese period label is stored on ``BaoCaoDaXuat.ky``; the file
    name uses an ASCII period fragment so downloads are portable.
    """
    now = now or timezone.localtime()
    scope = phong.ma_phong if phong is not None else "toan-trung-tam"
    timestamp = now.strftime("%Y%m%d-%H%M%S-%f")
    token = uuid4().hex[:6]
    extension = DinhDangXuat(dinh_dang).value
    return f"{scope}_{period_slug(period)}_{timestamp}_{token}.{extension}"


@transaction.atomic
def create_export_record(
    *,
    period_label: str,
    phong,
    user,
    dinh_dang: str,
    filename: str,
    content: bytes,
    reports: list[DepartmentReport],
    accepted: bool,
) -> BaoCaoDaXuat:
    record = BaoCaoDaXuat(
        ky=period_label,
        phong=phong,
        nguoi_lap=user,
        dinh_dang=dinh_dang,
    )
    record.file.save(filename, ContentFile(content), save=False)
    record.save()

    rows = []
    for report in reports:
        for row in report.rows:
            rows.append(
                BaoCaoDaXuatDong(
                    bao_cao=record,
                    chi_tieu_id=row.chi_tieu_id,
                    ten_chi_tieu=row.ten_chi_tieu,
                    phong_id=report.phong.pk,
                    period_value=row.period_value,
                    cumulative=row.cumulative,
                    plan=row.plan,
                    percent=row.percent,
                    note=(
                        GAP_NOTE
                        if accepted
                        and row.chi_tieu_id in report.affected_ids
                        else ""
                    ),
                    danh_gia=report.notes.get(row.chi_tieu_id, ""),
                    breakdown_label=breakdown_label(row),
                )
            )
    BaoCaoDaXuatDong.objects.bulk_create(rows)
    return record


def content_stream(content: bytes) -> BytesIO:
    stream = BytesIO(content)
    stream.seek(0)
    return stream
