"""The demo loader still points at the retired catalog codes."""

from django.core.management.base import BaseCommand, CommandError


class Command(BaseCommand):
    help = (
        "Không chạy được. Dữ liệu demo vẫn trỏ HTKN-LOP, GDCN-HS và "
        "TTTK-NDT. Danh mục GDCN nay nạp bằng seed_gdcn."
    )

    def handle(self, *args, **options):
        raise CommandError(
            "seed_demo_data không còn chạy. Dữ liệu demo vẫn trỏ các mã "
            "HTKN-LOP, GDCN-HS và TTTK-NDT của catalog cũ. Danh mục Phòng "
            "Giao dịch công nghệ nạp bằng: python manage.py seed_gdcn"
        )
