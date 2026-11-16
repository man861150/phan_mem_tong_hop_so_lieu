"""Load the GDCN catalog from the 6 rõ workbook."""

from pathlib import Path

from django.core.management.base import BaseCommand
from django.utils import timezone

from apps.catalog.seed_gdcn import (
    DEV_PASSWORDS,
    apply_seed,
    default_workbook,
    parse_workbook,
    render_plan,
)


class Command(BaseCommand):
    help = (
        "Nạp phòng GDCN, tài khoản dev và danh mục từ workbook 6 rõ. "
        "Chạy lại không tạo bản ghi trùng. Mật khẩu chỉ dùng trên máy dev: "
        + ", ".join(f"{username}={password}" for username, password in DEV_PASSWORDS)
        + "."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--file",
            default="",
            help="Đường dẫn workbook .xlsx. Mặc định là file GDCN trong doc/.",
        )
        parser.add_argument(
            "--year",
            type=int,
            default=None,
            help="Năm của chỉ tiêu kế hoạch. Mặc định là năm hiện tại.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="In cây sẽ ghi và không ghi cơ sở dữ liệu.",
        )

    def handle(self, *args, **options):
        year = options["year"] or timezone.localdate().year
        path = Path(options["file"]) if options["file"] else default_workbook()
        plan = parse_workbook(path)
        self.stdout.write(render_plan(plan, year))
        if options["dry_run"]:
            self.stdout.write("Dry-run: không ghi cơ sở dữ liệu.")
            return
        for line in apply_seed(plan, year):
            self.stdout.write(line)
