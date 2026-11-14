"""Idempotent localhost demo data across every application-owned table."""

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.management.commands.seed_localhost import seed_localhost
from apps.catalog.management.commands.load_linh_vuc import (
    CONFIRMATION,
    load_linh_vuc,
)
from apps.catalog.seed_data import seed_catalog
from apps.reporting.demo_seed import (
    assert_local_database,
    build_catalog,
    seed_demo_atomic,
)


class Command(BaseCommand):
    help = (
        "Nạp dữ liệu mẫu đầy đủ cho website trên database localhost solieu. "
        "Bao gồm phòng ban, tài khoản dev, danh mục, kỳ báo cáo, hoạt động, "
        "dự án, phiếu, số liệu, lịch sử xử lý và báo cáo đã xuất. "
        "Chạy lại không tạo bản ghi trùng."
    )

    def handle(self, *args, **options):
        assert_local_database()
        lines = []
        lines.extend(seed_localhost())
        lines.extend(seed_catalog())

        csv_path = settings.BASE_DIR / "fixtures" / "linh_vuc.csv"
        if not csv_path.is_file():
            raise CommandError(
                "Chưa có fixtures/linh_vuc.csv. Không thể seed lĩnh vực mẫu."
            )
        counts = load_linh_vuc(csv_path)
        lines.append(
            "linh_vuc: "
            f"created={counts['created']} updated={counts['updated']} "
            f"unchanged={counts['unchanged']}. {CONFIRMATION}"
        )

        catalogs = build_catalog()
        lines.extend(seed_demo_atomic(catalogs))
        for line in lines:
            self.stdout.write(line)
