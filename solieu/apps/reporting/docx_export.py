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
from apps.reporting.xlsx_export import check_export_size

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
            "noi_dung": activity.get("noi_dung", ""),
            "ket_qua": activity.get("ket_qua", ""),
        }
        for activity in report.activities
    ]
    items.extend(
        {
            "ten": project["du_an"],
            "thoi_gian": project["ngay"],
            "trang_thai": project["trang_thai"],
            "loai": f"Hỗ trợ dự án — {project['loai_ho_tro']}",
            "noi_dung": "",
            "ket_qua": "",
        }
        for project in report.projects
    )
    return items


def _breakdown_lines(report: DepartmentReport) -> list[str]:
    lines = []
    for breakdown in report.breakdowns:
        lines.append(
            f"{breakdown['chi_tieu']} ({breakdown['ma_chi_tieu']})"
        )
        for dimension in breakdown["dimensions"]:
            lines.append(f"  {dimension['ten']}")
            for item in dimension["items"]:
                lines.append(f"    • {item['ten']}: {item['value']}")
    return lines


def _center_detail_lines(reports: list[DepartmentReport]) -> list[str]:
    lines = []
    for report in reports:
        if report.breakdowns:
            lines.append(
                "PHÂN TÍCH THEO ĐỐI TƯỢNG VÀ LĨNH VỰC — "
                f"PHÒNG {report.ma_phong} — {report.ten}"
            )
            lines.extend(_breakdown_lines(report))
        items = _danh_sach(report)
        if report.ma_phong == "HTKN" and items:
            lines.append(
                f"DANH SÁCH HOẠT ĐỘNG VÀ DỰ ÁN HỖ TRỢ — PHÒNG {report.ten}"
            )
            for item in items:
                line = (
                    f"• {item['ten']} — {item['loai']} — "
                    f"{item['thoi_gian']} — {item['trang_thai']}"
                )
                if item["noi_dung"]:
                    line += f" — Nội dung: {item['noi_dung']}"
                if item["ket_qua"]:
                    line += f" — Kết quả: {item['ket_qua']}"
                lines.append(line)
    return lines


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
    check_export_size(reports)
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
            "breakdown_lines": _breakdown_lines(report),
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
                    "breakdown_lines": _breakdown_lines(report),
                }
                for report in reports
            ],
            "center_details": _center_detail_lines(reports),
            "ghi_chu_thieu": gap_summary(reports, accepted),
            "nguoi_lap": user_label,
            "ngay_lap": generated_at.strftime("%d/%m/%Y %H:%M"),
        }

    document = DocxTemplate(str(template_path))
    document.render(context)
    output = BytesIO()
    document.save(output)
    return output.getvalue()
