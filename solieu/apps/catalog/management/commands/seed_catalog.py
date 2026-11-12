"""Idempotent catalog for the three pilot departments."""

from django.core.management.base import BaseCommand

from apps.catalog.seed_data import seed_catalog


class Command(BaseCommand):
    help = (
        "Nạp danh mục chỉ tiêu của HTKN, GDCN và TTTK. "
        "Chạy lại không tạo bản ghi trùng và không sửa số kế hoạch đã có."
    )

    def handle(self, *args, **options):
        for line in seed_catalog():
            self.stdout.write(line)
