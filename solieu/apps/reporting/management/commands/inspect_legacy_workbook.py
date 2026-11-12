"""Print the structure of a legacy workbook without importing it."""

from __future__ import annotations

from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from openpyxl import load_workbook


def _doc_root() -> Path:
    candidates = [
        Path(settings.BASE_DIR).parent / "doc",
        Path(settings.BASE_DIR) / "doc",
    ]
    for candidate in candidates:
        if candidate.exists():
            return candidate.resolve()
    return candidates[0].resolve()


class Command(BaseCommand):
    help = (
        "In tên sheet và dòng không rỗng đầu tiên của một workbook trong doc/. "
        "Lệnh chỉ đọc, không ghi cơ sở dữ liệu."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "path",
            help="Đường dẫn tới tệp .xlsx, tuyệt đối hoặc tương đối trong doc/.",
        )

    def handle(self, *args, **options):
        doc_root = _doc_root()
        requested = Path(options["path"]).expanduser()
        if not requested.is_absolute():
            requested = doc_root / requested
        resolved = requested.resolve()
        if not resolved.is_relative_to(doc_root):
            raise CommandError("Đường dẫn phải nằm trong thư mục doc/.")
        if resolved.suffix.lower() != ".xlsx":
            raise CommandError("Chỉ hỗ trợ tệp .xlsx.")
        if not resolved.is_file():
            raise CommandError(f"Không tìm thấy tệp {resolved}.")

        try:
            workbook = load_workbook(
                resolved,
                read_only=True,
                data_only=True,
            )
        except Exception as exc:  # openpyxl raises several ZIP/XML errors.
            raise CommandError(f"Không đọc được workbook: {exc}") from exc

        self.stdout.write(f"Tệp: {resolved.name}")
        self.stdout.write(f"Danh sách sheet: {', '.join(workbook.sheetnames)}")
        for sheet in workbook.worksheets:
            self.stdout.write("")
            self.stdout.write(f"Sheet: {sheet.title}")
            first_row = None
            for row in sheet.iter_rows(values_only=True):
                if any(value not in (None, "") for value in row):
                    first_row = row
                    break
            if first_row is None:
                self.stdout.write("  (không có dòng không rỗng)")
                continue
            values = [
                value for value in first_row if value not in (None, "")
            ]
            self.stdout.write(f"  Dòng không rỗng đầu tiên: {values!r}")
