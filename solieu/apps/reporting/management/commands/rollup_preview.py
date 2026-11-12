"""Print the rollup for one period so M6 can be checked before screens exist."""

from decimal import ROUND_HALF_UP, Decimal

from django.core.management.base import BaseCommand, CommandError

from apps.catalog.models import PhongBan
from apps.reporting.rollup import ReportPeriod, rollup


def _format_number(value):
    if value is None:
        return "—"
    text = format(value, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


def _format_percent(value):
    if value is None:
        return "—"
    rounded = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    return _format_number(rounded)


class Command(BaseCommand):
    help = "Xem trước kết quả tổng hợp của một tháng hoặc một quý."

    def add_arguments(self, parser):
        parser.add_argument("--year", type=int, required=True)
        group = parser.add_mutually_exclusive_group(required=True)
        group.add_argument("--month", type=int)
        group.add_argument("--quarter", type=int)
        parser.add_argument("--phong", help="Mã phòng, ví dụ HTKN.")

    def handle(self, *args, **options):
        year = options["year"]
        try:
            if options["month"] is not None:
                period = ReportPeriod.month(year, options["month"])
            else:
                period = ReportPeriod.quarter(year, options["quarter"])
        except ValueError as exc:
            raise CommandError(str(exc)) from exc

        phong = None
        if options["phong"]:
            phong = PhongBan.objects.filter(
                ma_phong=options["phong"]
            ).first()
            if phong is None:
                raise CommandError(
                    f"Không tìm thấy phòng có mã {options['phong']}."
                )

        rows = rollup(
            period,
            department_id=phong.pk if phong else None,
        )
        if not rows:
            self.stdout.write("Không có số liệu.")
            return

        self.stdout.write(
            f"Kỳ {period.start:%d/%m/%Y} – {period.end:%d/%m/%Y}"
        )
        for row in rows:
            self.stdout.write("")
            self.stdout.write(
                f"{row.ma_chi_tieu} — {row.ten_chi_tieu}"
            )
            self.stdout.write(f"  Phòng: {row.ma_phong}")
            self.stdout.write(f"  Đơn vị tính: {row.don_vi_tinh}")
            self.stdout.write(
                f"  Giá trị trong kỳ: {_format_number(row.period_value)}"
            )
            self.stdout.write(
                f"  Lũy kế: {_format_number(row.cumulative)}"
            )
            self.stdout.write(f"  Kế hoạch: {_format_number(row.plan)}")
            self.stdout.write(
                f"  % hoàn thành: {_format_percent(row.percent)}"
            )
            self.stdout.write(
                f"  Chậm tiến độ: {'Có' if row.behind else 'Không'}"
            )
