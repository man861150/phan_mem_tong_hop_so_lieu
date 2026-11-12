"""Single aggregation entry point for dashboard, Excel, and Word.

SQL computes sum, count, cumulative, and latest. Python computes ratio,
average, percent of plan, remainder, and behind-schedule flags.

``rollup()`` is a read-only library function. Permission checks belong to the
caller; ``department_id`` here is only a data filter.
"""

from __future__ import annotations

import calendar
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.db.models import (
    Case,
    Count,
    DateField,
    F,
    Sum,
    Value,
    When,
)
from django.db.models.functions import Coalesce

from apps.catalog.models import (
    CachTongHop,
    ChiTieu,
    ChiTieuKeHoach,
    CountSubject,
    TrangThaiKeHoach,
)
from apps.entry.models import (
    HoTroDuAn,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)

ASIA_HO_CHI_MINH = ZoneInfo("Asia/Ho_Chi_Minh")
OFFICIAL_STATUS = TrangThaiPhieu.DA_DUYET
PENDING_STATUS = TrangThaiPhieu.CHO_DUYET
HUNDRED = Decimal("100")
PERIOD_KINDS = ("month", "quarter", "year")


@dataclass(frozen=True)
class ReportPeriod:
    """A report window: one month, one quarter, or one year.

    ``kind`` is ``month``, ``quarter``, or ``year``. The dates must match the
    declared kind exactly; use the constructors rather than building dates by
    hand.
    """

    year: int
    start: date
    end: date
    kind: str

    def __post_init__(self):
        if self.kind not in PERIOD_KINDS:
            raise ValueError(f"Loại kỳ không hợp lệ: {self.kind!r}.")
        if self.year < 1:
            raise ValueError("Năm báo cáo phải là số dương.")
        if self.start.year != self.year or self.end.year != self.year:
            raise ValueError("Khoảng ngày phải nằm trong năm báo cáo.")
        if self.start > self.end:
            raise ValueError("Ngày bắt đầu phải không sau ngày kết thúc.")
        self._validate_shape()

    def _validate_shape(self):
        if self.kind == "month":
            if not (
                self.start.day == 1
                and self.start.month == self.end.month
                and self.end.day
                == calendar.monthrange(self.year, self.end.month)[1]
            ):
                raise ValueError("Kỳ tháng phải là trọn một tháng.")
            return
        if self.kind == "quarter":
            if self.start.month not in (1, 4, 7, 10) or self.start.day != 1:
                raise ValueError("Kỳ quý phải bắt đầu vào ngày đầu quý.")
            end_month = self.start.month + 2
            if not (
                self.end.month == end_month
                and self.end.day == calendar.monthrange(self.year, end_month)[1]
            ):
                raise ValueError("Kỳ quý phải kết thúc vào ngày cuối quý.")
            return
        if not (
            self.start.month == 1
            and self.start.day == 1
            and self.end.month == 12
            and self.end.day == 31
        ):
            raise ValueError("Kỳ năm phải là trọn một năm dương lịch.")

    @classmethod
    def month(cls, year: int, month: int) -> ReportPeriod:
        if not 1 <= month <= 12:
            raise ValueError("Tháng phải từ 1 đến 12.")
        last_day = calendar.monthrange(year, month)[1]
        return cls(
            year=year,
            start=date(year, month, 1),
            end=date(year, month, last_day),
            kind="month",
        )

    @classmethod
    def quarter(cls, year: int, quarter: int) -> ReportPeriod:
        if not 1 <= quarter <= 4:
            raise ValueError("Quý phải từ 1 đến 4.")
        start_month = 3 * (quarter - 1) + 1
        end_month = start_month + 2
        last_day = calendar.monthrange(year, end_month)[1]
        return cls(
            year=year,
            start=date(year, start_month, 1),
            end=date(year, end_month, last_day),
            kind="quarter",
        )

    @classmethod
    def annual(cls, year: int) -> ReportPeriod:
        return cls(
            year=year,
            start=date(year, 1, 1),
            end=date(year, 12, 31),
            kind="year",
        )


@dataclass(frozen=True)
class BreakdownRow:
    """One split value inside a result row."""

    id: int
    ma: str
    ten: str
    value: Decimal | None


@dataclass(frozen=True)
class RollupRow:
    """One indicator's result. This is a value object, never a saved model."""

    chi_tieu_id: int
    ma_chi_tieu: str
    ten_chi_tieu: str
    don_vi_tinh: str
    cach_tong_hop: str
    phong_id: int
    ma_phong: str
    ten_phong: str
    period_value: Decimal | None
    cumulative: Decimal | None
    plan: Decimal | None
    percent: Decimal | None
    remainder: Decimal | None
    behind: bool
    pending_period_value: Decimal | None = None
    pending_cumulative: Decimal | None = None
    doi_tuong: list[BreakdownRow] = field(default_factory=list)
    linh_vuc: dict[str, list[BreakdownRow]] = field(
        default_factory=lambda: {"qd36": [], "tt24": []}
    )
    nguon: list[BreakdownRow] = field(default_factory=list)

    @property
    def reported_value(self) -> Decimal | None:
        """Cumulative is the primary value for cumulative indicators."""
        if self.cach_tong_hop == CachTongHop.CUMULATIVE:
            return self.cumulative
        return self.period_value


def _coerce_period(period) -> ReportPeriod:
    if isinstance(period, ReportPeriod):
        return period
    if isinstance(period, dict):
        return ReportPeriod(**period)
    required = ("year", "start", "end", "kind")
    if all(hasattr(period, name) for name in required):
        return ReportPeriod(
            year=period.year,
            start=period.start,
            end=period.end,
            kind=period.kind,
        )
    raise TypeError(
        "period phải là ReportPeriod hoặc có year, start, end, kind."
    )


def _attribution_expression():
    activity_date = Coalesce(
        "phieu__hoat_dong__den_ngay",
        "phieu__hoat_dong__tu_ngay",
        output_field=DateField(),
    )
    monthly_date = Coalesce(
        "phieu__ky__den_ngay",
        "phieu__ky__tu_ngay",
        output_field=DateField(),
    )
    return Case(
        When(phieu__loai_phieu=LoaiPhieu.HOAT_DONG, then=activity_date),
        When(phieu__loai_phieu=LoaiPhieu.THANG, then=monthly_date),
        default=Value(None, output_field=DateField()),
        output_field=DateField(),
    )


def _solieu_queryset(start, end, status, department_id):
    qs = SoLieu.objects.filter(
        phieu__trang_thai=status,
        phieu__loai_phieu__in=(LoaiPhieu.HOAT_DONG, LoaiPhieu.THANG),
    ).filter(phieu__phong_id=F("chi_tieu__nhom__phong_id"))
    if department_id is not None:
        qs = qs.filter(phieu__phong_id=department_id)
    qs = qs.annotate(attribution_date=_attribution_expression())
    return qs.filter(
        attribution_date__gte=start,
        attribution_date__lte=end,
    )


def _total_rows(qs):
    return qs.filter(doi_tuong__isnull=True, linh_vuc__isnull=True)


def _sum_map(qs):
    rows = (
        _total_rows(qs)
        .values("chi_tieu_id", "phieu__phong_id")
        .annotate(value=Sum("gia_tri"))
    )
    return {
        (row["chi_tieu_id"], row["phieu__phong_id"]): row["value"]
        for row in rows
    }


def _average_map(qs):
    """SQL supplies sum and count; Python performs the division."""
    rows = (
        _total_rows(qs)
        .values("chi_tieu_id", "phieu__phong_id")
        .annotate(total=Sum("gia_tri"), count=Count("gia_tri"))
    )
    averages = {}
    for row in rows:
        key = (row["chi_tieu_id"], row["phieu__phong_id"])
        count = row["count"]
        averages[key] = (
            row["total"] / Decimal(count) if count else None
        )
    return averages


def _latest_map(qs):
    rows = (
        _total_rows(qs)
        .filter(gia_tri__isnull=False)
        .values(
            "chi_tieu_id",
            "phieu__phong_id",
            "gia_tri",
            "attribution_date",
            "phieu_id",
        )
        .order_by(
            "chi_tieu_id",
            "phieu__phong_id",
            "-attribution_date",
            "-phieu_id",
        )
        .distinct("chi_tieu_id", "phieu__phong_id")
    )
    return {
        (row["chi_tieu_id"], row["phieu__phong_id"]): row["gia_tri"]
        for row in rows
    }


def _key_set(qs):
    return set(qs.values_list("chi_tieu_id", "phieu__phong_id"))


def _activity_count_queryset(start, end, status, department_id):
    attribution = Case(
        When(
            hoat_dong__den_ngay__isnull=False,
            then=F("hoat_dong__den_ngay"),
        ),
        default=F("hoat_dong__tu_ngay"),
        output_field=DateField(),
    )
    qs = PhieuNhapLieu.objects.filter(
        trang_thai=status,
        loai_phieu=LoaiPhieu.HOAT_DONG,
        la_phieu_bo_sung=False,
        hoat_dong__isnull=False,
        hoat_dong__loai_hoat_dong__isnull=False,
    ).filter(phong_id=F("hoat_dong__loai_hoat_dong__phong_id"))
    if department_id is not None:
        qs = qs.filter(phong_id=department_id)
    qs = qs.annotate(attribution_date=attribution)
    return qs.filter(
        attribution_date__gte=start,
        attribution_date__lte=end,
    )


def _project_count_queryset(start, end, status, department_id):
    qs = HoTroDuAn.objects.filter(
        phieu__trang_thai=status,
        phieu__loai_phieu=LoaiPhieu.DU_AN,
        ngay_ho_tro__gte=start,
        ngay_ho_tro__lte=end,
    ).filter(
        phieu__du_an_id=F("du_an_id"),
        phieu__phong_id=F("du_an__phong_id"),
    )
    if department_id is not None:
        qs = qs.filter(phieu__phong_id=department_id)
    return qs


def _activity_count_map(qs):
    rows = (
        qs.values("hoat_dong__loai_hoat_dong_id", "phong_id")
        .annotate(value=Count("hoat_dong_id", distinct=True))
        .order_by()
    )
    return {
        (row["hoat_dong__loai_hoat_dong_id"], row["phong_id"]): Decimal(
            row["value"]
        )
        for row in rows
    }


def _project_count_map(qs):
    rows = (
        qs.values("loai_ho_tro", "phieu__phong_id")
        .annotate(value=Count("du_an_id", distinct=True))
        .order_by()
    )
    return {
        (row["loai_ho_tro"], row["phieu__phong_id"]): Decimal(row["value"])
        for row in rows
    }


def _plan_map(year, department_id):
    qs = ChiTieuKeHoach.objects.filter(
        nam=year,
        trang_thai=TrangThaiKeHoach.DA_XAC_NHAN,
    )
    if department_id is not None:
        qs = qs.filter(chi_tieu__nhom__phong_id=department_id)
    rows = qs.values(
        "chi_tieu_id",
        "chi_tieu__nhom__phong_id",
        "doi_tuong_id",
        "gia_tri_ke_hoach",
    )
    totals = {}
    object_values = defaultdict(lambda: Decimal("0"))
    object_has_value = set()
    object_keys = set()
    for row in rows:
        key = (
            row["chi_tieu_id"],
            row["chi_tieu__nhom__phong_id"],
        )
        value = row["gia_tri_ke_hoach"]
        if row["doi_tuong_id"] is None:
            totals[key] = value
        else:
            object_keys.add(key)
            if value is not None:
                object_values[key] += value
                object_has_value.add(key)
    plans = {}
    for key in set(totals) | object_keys:
        total = totals.get(key)
        if total is not None:
            plans[key] = total
        elif key in object_has_value:
            plans[key] = object_values[key]
        else:
            plans[key] = None
    return plans


def _breakdown_map(qs, dimension):
    if dimension == "doi_tuong":
        rows = (
            qs.filter(doi_tuong__isnull=False)
            .values(
                "chi_tieu_id",
                "phieu__phong_id",
                "doi_tuong_id",
                "doi_tuong__ten_doi_tuong",
            )
            .annotate(value=Sum("gia_tri"))
            .order_by("doi_tuong__ten_doi_tuong", "doi_tuong_id")
        )
        grouped = defaultdict(list)
        for row in rows:
            grouped[
                (row["chi_tieu_id"], row["phieu__phong_id"])
            ].append(
                BreakdownRow(
                    id=row["doi_tuong_id"],
                    ma="",
                    ten=row["doi_tuong__ten_doi_tuong"],
                    value=row["value"],
                )
            )
        return grouped

    if dimension == "linh_vuc":
        rows = (
            qs.filter(linh_vuc__isnull=False)
            .values(
                "chi_tieu_id",
                "phieu__phong_id",
                "linh_vuc_id",
                "linh_vuc__he_thong",
                "linh_vuc__ma",
                "linh_vuc__ten",
            )
            .annotate(value=Sum("gia_tri"))
            .order_by("linh_vuc__he_thong", "linh_vuc__ma", "linh_vuc_id")
        )
        grouped = defaultdict(lambda: {"qd36": [], "tt24": []})
        for row in rows:
            key = (row["chi_tieu_id"], row["phieu__phong_id"])
            system = row["linh_vuc__he_thong"]
            grouped[key].setdefault(system, []).append(
                BreakdownRow(
                    id=row["linh_vuc_id"],
                    ma=row["linh_vuc__ma"],
                    ten=row["linh_vuc__ten"],
                    value=row["value"],
                )
            )
        return grouped

    # Nguồn is a property of the total row. Restricting it to total rows
    # avoids adding a total and its splits twice.
    rows = (
        _total_rows(qs)
        .filter(nguon__isnull=False)
        .values(
            "chi_tieu_id",
            "phieu__phong_id",
            "nguon_id",
            "nguon__ten_nguon",
        )
        .annotate(value=Sum("gia_tri"))
        .order_by("nguon__ten_nguon", "nguon_id")
    )
    grouped = defaultdict(list)
    for row in rows:
        grouped[(row["chi_tieu_id"], row["phieu__phong_id"])].append(
            BreakdownRow(
                id=row["nguon_id"],
                ma="",
                ten=row["nguon__ten_nguon"],
                value=row["value"],
            )
        )
    return grouped


def _ratio(numerator, denominator):
    if numerator is None or denominator is None or denominator == 0:
        return None
    return numerator / denominator


def _elapsed_fraction(period):
    today = datetime.now(ASIA_HO_CHI_MINH).date()
    as_of = min(period.end, today)
    year_start = date(period.year, 1, 1)
    next_year = date(period.year + 1, 1, 1)
    if as_of < year_start:
        return Decimal("0")
    if as_of >= next_year:
        return Decimal("1")
    elapsed = (as_of - year_start).days + 1
    total = (next_year - year_start).days
    return Decimal(elapsed) / Decimal(total)


def _percentage(cumulative, plan):
    if plan is None or plan == 0 or cumulative is None:
        return None, None
    return cumulative / plan * HUNDRED, plan - cumulative


def _ratio_indicators(department_id):
    qs = ChiTieu.objects.filter(
        cach_tong_hop=CachTongHop.RATIO
    ).select_related("nhom__phong")
    if department_id is not None:
        qs = qs.filter(nhom__phong_id=department_id)
    return list(qs)


def _count_indicators(department_id):
    qs = ChiTieu.objects.filter(
        cach_tong_hop=CachTongHop.COUNT
    ).select_related("nhom__phong")
    if department_id is not None:
        qs = qs.filter(nhom__phong_id=department_id)
    return list(qs)


def _add_count_keys(
    keys,
    plans,
    count_indicators,
    activity_period_counts,
    activity_cumulative_counts,
    project_period_counts,
    project_cumulative_counts,
    pending_activity_period_counts,
    pending_activity_cumulative_counts,
    pending_project_period_counts,
    pending_project_cumulative_counts,
    include_pending,
):
    for indicator in count_indicators:
        phong_id = indicator.nhom.phong_id
        indicator_key = (indicator.pk, phong_id)
        if indicator.count_subject == CountSubject.ACTIVITY:
            count_key = (indicator.loai_hoat_dong_id, phong_id)
            official_present = (
                count_key in activity_period_counts
                or count_key in activity_cumulative_counts
            )
            pending_present = include_pending and (
                count_key in pending_activity_period_counts
                or count_key in pending_activity_cumulative_counts
            )
        else:
            count_key = (indicator.loai_ho_tro, phong_id)
            official_present = (
                count_key in project_period_counts
                or count_key in project_cumulative_counts
            )
            pending_present = include_pending and (
                count_key in pending_project_period_counts
                or count_key in pending_project_cumulative_counts
            )
        if official_present or pending_present or indicator_key in plans:
            keys.add(indicator_key)


def _add_ratio_keys(keys, ratio_indicators):
    for indicator in ratio_indicators:
        phong_id = indicator.nhom.phong_id
        key = (indicator.pk, phong_id)
        if key in keys:
            continue
        numerator = (indicator.chi_tieu_tu_so_id, phong_id)
        denominator = (indicator.chi_tieu_mau_so_id, phong_id)
        if numerator in keys or denominator in keys:
            keys.add(key)


def rollup(period, *, department_id=None, include_pending=False):
    """Return aggregated indicator values for one reporting period.

    ``period`` is a :class:`ReportPeriod` (or an object/dict with ``year``,
    ``start``, ``end``, and ``kind``). ``department_id`` filters data; it is
    not a permission check. Pending figures are separate from official values.

    Breakdown lists are period sums of split rows. The source breakdown uses
    total rows so a total is not added to its own splits. Ratio operands use
    their total sums, matching the seeded catalog where both are ``sum``.
    """
    period = _coerce_period(period)
    year_start = date(period.year, 1, 1)

    official_period = _solieu_queryset(
        period.start, period.end, OFFICIAL_STATUS, department_id
    )
    official_cumulative = _solieu_queryset(
        year_start, period.end, OFFICIAL_STATUS, department_id
    )
    official_sum = _sum_map(official_period)
    official_cumulative_sum = _sum_map(official_cumulative)
    official_average = _average_map(official_period)
    official_cumulative_average = _average_map(official_cumulative)
    official_latest = _latest_map(official_period)
    official_cumulative_latest = _latest_map(official_cumulative)

    activity_period_counts = _activity_count_map(
        _activity_count_queryset(
            period.start, period.end, OFFICIAL_STATUS, department_id
        )
    )
    activity_cumulative_counts = _activity_count_map(
        _activity_count_queryset(
            year_start, period.end, OFFICIAL_STATUS, department_id
        )
    )
    project_period_counts = _project_count_map(
        _project_count_queryset(
            period.start, period.end, OFFICIAL_STATUS, department_id
        )
    )
    project_cumulative_counts = _project_count_map(
        _project_count_queryset(
            year_start, period.end, OFFICIAL_STATUS, department_id
        )
    )

    pending_period_sum = {}
    pending_cumulative_sum = {}
    pending_average = {}
    pending_cumulative_average = {}
    pending_latest = {}
    pending_cumulative_latest = {}
    pending_activity_period_counts = {}
    pending_activity_cumulative_counts = {}
    pending_project_period_counts = {}
    pending_project_cumulative_counts = {}
    if include_pending:
        pending_period = _solieu_queryset(
            period.start, period.end, PENDING_STATUS, department_id
        )
        pending_cumulative = _solieu_queryset(
            year_start, period.end, PENDING_STATUS, department_id
        )
        pending_period_sum = _sum_map(pending_period)
        pending_cumulative_sum = _sum_map(pending_cumulative)
        pending_average = _average_map(pending_period)
        pending_cumulative_average = _average_map(pending_cumulative)
        pending_latest = _latest_map(pending_period)
        pending_cumulative_latest = _latest_map(pending_cumulative)
        pending_activity_period_counts = _activity_count_map(
            _activity_count_queryset(
                period.start, period.end, PENDING_STATUS, department_id
            )
        )
        pending_activity_cumulative_counts = _activity_count_map(
            _activity_count_queryset(
                year_start, period.end, PENDING_STATUS, department_id
            )
        )
        pending_project_period_counts = _project_count_map(
            _project_count_queryset(
                period.start, period.end, PENDING_STATUS, department_id
            )
        )
        pending_project_cumulative_counts = _project_count_map(
            _project_count_queryset(
                year_start, period.end, PENDING_STATUS, department_id
            )
        )

    plans = _plan_map(period.year, department_id)

    keys = _key_set(official_period) | _key_set(official_cumulative)
    if include_pending:
        keys |= _key_set(pending_period) | _key_set(pending_cumulative)
    keys |= set(plans)

    count_indicators = _count_indicators(department_id)
    _add_count_keys(
        keys,
        plans,
        count_indicators,
        activity_period_counts,
        activity_cumulative_counts,
        project_period_counts,
        project_cumulative_counts,
        pending_activity_period_counts,
        pending_activity_cumulative_counts,
        pending_project_period_counts,
        pending_project_cumulative_counts,
        include_pending,
    )

    ratio_indicators = _ratio_indicators(department_id)
    _add_ratio_keys(keys, ratio_indicators)

    indicator_ids = {key[0] for key in keys}
    indicators = ChiTieu.objects.select_related("nhom__phong").in_bulk(
        indicator_ids
    )
    breakdown_doi_tuong = _breakdown_map(official_period, "doi_tuong")
    breakdown_linh_vuc = _breakdown_map(official_period, "linh_vuc")
    breakdown_nguon = _breakdown_map(official_period, "nguon")
    elapsed = _elapsed_fraction(period)

    rows = []
    for chi_tieu_id, _phong_id in keys:
        indicator = indicators.get(chi_tieu_id)
        if indicator is None:
            continue
        phong = indicator.nhom.phong
        if department_id is not None and phong.pk != department_id:
            continue
        key = (indicator.pk, phong.pk)
        mode = indicator.cach_tong_hop
        period_value = None
        cumulative = None
        pending_period_value = None
        pending_cumulative = None

        if mode in (CachTongHop.SUM, CachTongHop.CUMULATIVE):
            period_value = official_sum.get(key)
            cumulative = official_cumulative_sum.get(key)
            if include_pending:
                pending_period_value = pending_period_sum.get(key)
                pending_cumulative = pending_cumulative_sum.get(key)
        elif mode == CachTongHop.AVERAGE:
            period_value = official_average.get(key)
            cumulative = official_cumulative_average.get(key)
            if include_pending:
                pending_period_value = pending_average.get(key)
                pending_cumulative = pending_cumulative_average.get(key)
        elif mode == CachTongHop.LATEST:
            period_value = official_latest.get(key)
            cumulative = official_cumulative_latest.get(key)
            if include_pending:
                pending_period_value = pending_latest.get(key)
                pending_cumulative = pending_cumulative_latest.get(key)
        elif mode == CachTongHop.RATIO:
            numerator_id = indicator.chi_tieu_tu_so_id
            denominator_id = indicator.chi_tieu_mau_so_id
            period_value = _ratio(
                official_sum.get((numerator_id, phong.pk)),
                official_sum.get((denominator_id, phong.pk)),
            )
            cumulative = _ratio(
                official_cumulative_sum.get((numerator_id, phong.pk)),
                official_cumulative_sum.get((denominator_id, phong.pk)),
            )
            if include_pending:
                pending_period_value = _ratio(
                    pending_period_sum.get((numerator_id, phong.pk)),
                    pending_period_sum.get((denominator_id, phong.pk)),
                )
                pending_cumulative = _ratio(
                    pending_cumulative_sum.get((numerator_id, phong.pk)),
                    pending_cumulative_sum.get((denominator_id, phong.pk)),
                )
        elif mode == CachTongHop.COUNT:
            if indicator.count_subject == CountSubject.ACTIVITY:
                count_key = (indicator.loai_hoat_dong_id, phong.pk)
                official_present = (
                    count_key in activity_period_counts
                    or count_key in activity_cumulative_counts
                )
                if official_present or key in plans:
                    period_value = activity_period_counts.get(
                        count_key, Decimal("0")
                    )
                    cumulative = activity_cumulative_counts.get(
                        count_key, Decimal("0")
                    )
                if include_pending:
                    pending_period_value = (
                        pending_activity_period_counts.get(count_key)
                    )
                    pending_cumulative = (
                        pending_activity_cumulative_counts.get(count_key)
                    )
            else:
                count_key = (indicator.loai_ho_tro, phong.pk)
                official_present = (
                    count_key in project_period_counts
                    or count_key in project_cumulative_counts
                )
                if official_present or key in plans:
                    period_value = project_period_counts.get(
                        count_key, Decimal("0")
                    )
                    cumulative = project_cumulative_counts.get(
                        count_key, Decimal("0")
                    )
                if include_pending:
                    pending_period_value = pending_project_period_counts.get(
                        count_key
                    )
                    pending_cumulative = pending_project_cumulative_counts.get(
                        count_key
                    )

        plan = plans.get(key)
        percent, remainder = _percentage(cumulative, plan)
        behind = percent is not None and percent < elapsed * HUNDRED

        breakdowns = {}
        if mode in (CachTongHop.SUM, CachTongHop.CUMULATIVE):
            breakdowns = {
                "doi_tuong": list(breakdown_doi_tuong.get(key, [])),
                "linh_vuc": dict(
                    breakdown_linh_vuc.get(
                        key, {"qd36": [], "tt24": []}
                    )
                ),
                "nguon": list(breakdown_nguon.get(key, [])),
            }

        rows.append(
            RollupRow(
                chi_tieu_id=indicator.pk,
                ma_chi_tieu=indicator.ma_chi_tieu,
                ten_chi_tieu=indicator.ten_chi_tieu,
                don_vi_tinh=indicator.don_vi_tinh,
                cach_tong_hop=mode,
                phong_id=phong.pk,
                ma_phong=phong.ma_phong,
                ten_phong=phong.ten_phong,
                period_value=period_value,
                cumulative=cumulative,
                plan=plan,
                percent=percent,
                remainder=remainder,
                behind=behind,
                pending_period_value=pending_period_value,
                pending_cumulative=pending_cumulative,
                doi_tuong=breakdowns.get("doi_tuong", []),
                linh_vuc=breakdowns.get(
                    "linh_vuc", {"qd36": [], "tt24": []}
                ),
                nguon=breakdowns.get("nguon", []),
            )
        )

    return sorted(rows, key=lambda row: (row.ma_phong, row.ma_chi_tieu))
