"""Fill the department and center Word templates with rollup values."""

from __future__ import annotations

from datetime import datetime
from io import BytesIO
from pathlib import Path

from django.conf import settings
from django.utils import timezone
from docxtpl import DocxTemplate

from apps.reporting.formatting import format_vi_number
from apps.reporting.report_data import (
    GAP_NOTE,
    DepartmentReport,
    gap_summary,
)

TEMPLATE_DIR = Path(settings.BASE_DIR) / "report_templates"


def _word_row(
    report: DepartmentReport,
    row,
    *,
    accepted: bool,
) -> dict:
    note = GAP_NOTE if accepted and row.chi_tieu_id in report.affected_ids else ""
    return {
        "chi_tieu": row.ten_chi_tieu,
        "don_vi_tinh": row.don_vi_tinh,
        "ke_hoach": format_vi_number(row.plan),
        "thuc_hien": format_vi_number(row.period_value),
        "luy_ke": format_vi_number(row.cumulative),
        "phan_tram": format_vi_number(row.percent),
        "ghi_chu": note,
        "danh_gia": report.notes.get(row.chi_tieu_id, ""),
    }


def _danh_sach(report: DepartmentReport) -> list[dict]:
    items = [
        {
            "ten": activity["ten"],
            "thoi_gian": activity["thoi_gian"],
            "trang_thai": activity["trang_thai"],
            "loai": activity["loai"],
        }
        for activity in report.activities
    ]
    items.extend(
        {
            "ten": project["du_an"],
            "thoi_gian": project["ngay"],
            "trang_thai": project["trang_thai"],
            "loai": f"Hỗ trợ dự án — {project['loai_ho_tro']}",
        }
        for project in report.projects
    )
    return items


def _template_name(reports: list[DepartmentReport], is_center: bool) -> str:
    if not is_center and reports:
        return f"{reports[0].phong.ma_phong.lower()}.docx"
    return "trung_tam.docx"


def build_docx(
    reports: list[DepartmentReport],
    *,
    period_label: str,
    accepted: bool,
    user_label: str,
    is_center: bool,
    generated_at: datetime | None = None,
) -> bytes:
    generated_at = generated_at or timezone.localtime()
    template_name = _template_name(reports, is_center)
    template_path = TEMPLATE_DIR / template_name
    if not template_path.exists():
        raise FileNotFoundError(f"Không tìm thấy mẫu Word {template_path.name}.")

    if not is_center and reports:
        report = reports[0]
        context = {
            "ky": period_label,
            "ma_phong": report.ma_phong,
            "ten_phong": report.ten,
            "rows": [
                _word_row(report, row, accepted=accepted)
                for row in report.rows
            ],
            "danh_sach": _danh_sach(report),
            "ghi_chu_thieu": gap_summary(reports, accepted),
            "nguoi_lap": user_label,
            "ngay_lap": generated_at.strftime("%d/%m/%Y %H:%M"),
        }
    else:
        context = {
            "ky": period_label,
            "departments": [
                {
                    "ma": report.ma_phong,
                    "ten": report.ten,
                    "rows": [
                        _word_row(report, row, accepted=accepted)
                        for row in report.rows
                    ],
                    "danh_sach": _danh_sach(report),
                }
                for report in reports
            ],
            "ghi_chu_thieu": gap_summary(reports, accepted),
            "nguoi_lap": user_label,
            "ngay_lap": generated_at.strftime("%d/%m/%Y %H:%M"),
        }

    document = DocxTemplate(str(template_path))
    document.render(context)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
