"""Data-entry forms, indicator rows, project support, and approvals."""

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation

from django import forms
from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone

from apps.activities.models import HoatDong
from apps.catalog.models import (
    BieuMauChiTieu,
    CachTongHop,
    ChiTieu,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    HeThongLinhVuc,
    KieuGhiNhan,
    NguonSoLieu,
)
from apps.entry.models import HoTroDuAn, SoLieu

ZERO = Decimal("0")
SOURCE_SURVEY = "Phiếu khảo sát sau sự kiện"


def _format_bound(value):
    """Render a Decimal bound without trailing zeros."""
    text = format(Decimal(value).normalize(), "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text


@dataclass(frozen=True)
class IndicatorLine:
    """One indicator shown on an entry form."""

    chi_tieu: ChiTieu
    bat_buoc: bool = False


def _number_field(label, **kwargs):
    return forms.DecimalField(
        label=label,
        required=False,
        min_value=ZERO,
        max_digits=18,
        decimal_places=4,
        localize=False,
        error_messages={
            "invalid": "Nhập một số hợp lệ.",
            "min_value": "Giá trị không được âm.",
            "max_digits": "Số vượt quá độ dài cho phép.",
            "max_decimal_places": "Chỉ nhập tối đa 4 chữ số thập phân.",
        },
        **kwargs,
    )


class IndicatorEntryForm(forms.Form):
    """Indicator rows generated from ``BieuMauChiTieu`` or monthly indicators.

    The form validates everything it can from the values at hand: non-negative
    numbers, source choices, ``khong_vuot_chi_tieu`` pairs, and split sums
    against the total row.  Draft saving deliberately does not check
    ``bat_buoc`` rows.  ``validate_required()`` is the extra gate for submit.

    M5-T02 must call ``validate_required()`` after ``is_valid()`` and before
    moving a phiếu to ``cho_duyet``.  There is no submit route in this
    milestone.
    """

    def __init__(
        self,
        *args,
        phieu=None,
        indicators=None,
        default_nguon_name=None,
        **kwargs,
    ):
        self.phieu = phieu
        self.indicators = list(indicators or [])
        self.default_nguon_name = default_nguon_name
        self.object_options = {}
        self.linh_vuc_map = {}
        self.linh_vuc_systems = {code: False for code in HeThongLinhVuc.values}
        self.lv_errors = {}
        self.parsed_field_rows = {}
        super().__init__(*args, **kwargs)
        self._add_fields()
        self._load_initial()
        self._load_linh_vuc_systems()

    def _load_linh_vuc_systems(self):
        if not any(line.chi_tieu.phan_loai_linh_vuc for line in self.indicators):
            return
        systems = set(
            DanhMucLinhVuc.objects.values_list("he_thong", flat=True).distinct()
        )
        self.linh_vuc_systems = {
            code: code in systems for code in HeThongLinhVuc.values
        }

    # ------------------------------------------------------------------
    # Field construction
    # ------------------------------------------------------------------
    def _add_fields(self):
        for line in self.indicators:
            chi_tieu = line.chi_tieu
            total_name = f"gia_tri_{chi_tieu.pk}"
            self.fields[total_name] = _number_field(
                chi_tieu.ten_chi_tieu,
                widget=forms.NumberInput(
                    attrs={
                        "step": "0.0001",
                        "min": "0",
                        "class": "form-control",
                    }
                ),
            )

            allowed = chi_tieu.nguon_cho_phep.all()
            sources = (
                allowed if allowed.exists() else NguonSoLieu.objects.all()
            ).order_by("ten_nguon")
            self.fields[f"nguon_{chi_tieu.pk}"] = forms.ModelChoiceField(
                label="Nguồn số liệu",
                queryset=sources,
                required=False,
                empty_label="— Không chọn —",
                error_messages={
                    "invalid_choice": "Nguồn số liệu không hợp lệ cho chỉ tiêu này."
                },
                widget=forms.Select(attrs={"class": "form-select"}),
            )

            self.object_options[chi_tieu.pk] = []
            if chi_tieu.phan_loai_doi_tuong:
                applicable = chi_tieu.doi_tuong_ap_dung.all()
                objects = (
                    applicable
                    if applicable.exists()
                    else DanhMucDoiTuong.objects.all()
                ).order_by("ten_doi_tuong")
                self.object_options[chi_tieu.pk] = list(objects)
                for doi_tuong in self.object_options[chi_tieu.pk]:
                    field_name = (
                        f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}"
                    )
                    self.fields[field_name] = _number_field(
                        doi_tuong.ten_doi_tuong,
                        widget=forms.NumberInput(
                            attrs={
                                "step": "0.0001",
                                "min": "0",
                                "class": "form-control",
                                "data-split-part": str(chi_tieu.pk),
                            }
                        ),
                    )

            if chi_tieu.phan_loai_linh_vuc:
                # A hidden field lets row-level split errors mark the form
                # invalid while the row message renders beside the grid.
                self.fields[f"linh_vuc_grid_{chi_tieu.pk}"] = forms.CharField(
                    required=False,
                    widget=forms.HiddenInput,
                )

    def _load_initial(self):
        existing = {}
        if self.phieu is not None and self.phieu.pk:
            rows = SoLieu.objects.filter(
                phieu=self.phieu,
                chi_tieu_id__in=[line.chi_tieu.pk for line in self.indicators],
            ).select_related("doi_tuong", "linh_vuc", "nguon")
            existing = {
                (row.chi_tieu_id, row.doi_tuong_id, row.linh_vuc_id): row
                for row in rows
            }
        self.existing = existing

        default_source = None
        if self.default_nguon_name:
            default_source = NguonSoLieu.objects.filter(
                ten_nguon=self.default_nguon_name
            ).first()

        for line in self.indicators:
            chi_tieu = line.chi_tieu
            total_name = f"gia_tri_{chi_tieu.pk}"
            source_name = f"nguon_{chi_tieu.pk}"
            total_row = existing.get((chi_tieu.pk, None, None))
            if total_row is not None:
                self.fields[total_name].initial = total_row.gia_tri
                self.fields[source_name].initial = total_row.nguon_id
            elif default_source is not None:
                if self.fields[source_name].queryset.filter(
                    pk=default_source.pk
                ).exists():
                    self.fields[source_name].initial = default_source.pk
            for doi_tuong in self.object_options[chi_tieu.pk]:
                split_row = existing.get((chi_tieu.pk, doi_tuong.pk, None))
                if split_row is not None:
                    field_name = f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}"
                    self.fields[field_name].initial = split_row.gia_tri

    # ------------------------------------------------------------------
    # Presentation helpers used by the templates
    # ------------------------------------------------------------------
    def presentation_rows(self):
        rows = []
        for line in self.indicators:
            chi_tieu = line.chi_tieu
            row = {
                "chi_tieu": chi_tieu,
                "bat_buoc": line.bat_buoc,
                "total": self[f"gia_tri_{chi_tieu.pk}"],
                "nguon": self[f"nguon_{chi_tieu.pk}"],
                "nguon_display": self._source_display(chi_tieu),
                "object_rows": [],
                "has_object": chi_tieu.phan_loai_doi_tuong,
                "has_linh_vuc": chi_tieu.phan_loai_linh_vuc,
                "linh_vuc_groups": {"qd36": [], "tt24": []},
                "linh_vuc_available": self.linh_vuc_systems,
                "grid_error": None,
                "previous": getattr(self, "previous_values", {}).get(
                    chi_tieu.pk
                ),
                "cumulative": getattr(self, "cumulative_values", {}).get(
                    chi_tieu.pk
                ),
            }
            if chi_tieu.phan_loai_doi_tuong:
                row["object_rows"] = [
                    {
                        "doi_tuong": doi_tuong,
                        "field": self[
                            f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}"
                        ],
                    }
                    for doi_tuong in self.object_options[chi_tieu.pk]
                ]
            if chi_tieu.phan_loai_linh_vuc:
                row["grid_error"] = self[f"linh_vuc_grid_{chi_tieu.pk}"]
                for item in self._field_items(chi_tieu):
                    system = item.get("he_thong") or HeThongLinhVuc.QD36
                    if system not in row["linh_vuc_groups"]:
                        system = HeThongLinhVuc.QD36
                    row["linh_vuc_groups"][system].append(item)
            rows.append(row)
        return rows

    def _source_display(self, chi_tieu):
        field_name = f"nguon_{chi_tieu.pk}"
        raw = None
        if self.is_bound:
            raw = self.data.get(field_name)
        else:
            raw = self.fields[field_name].initial
        if raw in (None, ""):
            return None
        try:
            return NguonSoLieu.objects.filter(pk=int(raw)).first()
        except (TypeError, ValueError):
            return None

    def _field_items(self, chi_tieu):
        if self.is_bound and chi_tieu.pk in self.parsed_field_rows:
            items = []
            for parsed in self.parsed_field_rows[chi_tieu.pk]:
                linh_vuc = self.linh_vuc_map.get(parsed["linh_vuc_id"])
                items.append(
                    {
                        "linh_vuc_id": parsed["linh_vuc_id"],
                        "linh_vuc": linh_vuc,
                        "he_thong": (
                            linh_vuc.he_thong if linh_vuc is not None else None
                        ),
                        "raw_value": parsed["raw_value"],
                        "error": parsed["error"],
                    }
                )
            return items
        items = []
        for (chi_tieu_id, _doi_tuong_id, linh_vuc_id), row in self.existing.items():
            if chi_tieu_id != chi_tieu.pk or linh_vuc_id is None:
                continue
            linh_vuc = row.linh_vuc
            items.append(
                {
                    "linh_vuc_id": linh_vuc_id,
                    "linh_vuc": linh_vuc,
                    "he_thong": (
                        linh_vuc.he_thong if linh_vuc is not None else None
                    ),
                    "raw_value": row.gia_tri,
                    "error": "",
                }
            )
        return items

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------
    def clean(self):
        cleaned = super().clean()
        self.lv_errors = {}
        self.parsed_field_rows = {}

        values = {
            line.chi_tieu.pk: cleaned.get(f"gia_tri_{line.chi_tieu.pk}")
            for line in self.indicators
        }

        for line in self.indicators:
            chi_tieu = line.chi_tieu
            source = cleaned.get(f"nguon_{chi_tieu.pk}")
            if source is not None and values[chi_tieu.pk] is None:
                self.add_error(
                    f"gia_tri_{chi_tieu.pk}",
                    "Nhập giá trị trước khi chọn nguồn số liệu.",
                )
            if chi_tieu.phan_loai_linh_vuc:
                self.parsed_field_rows[chi_tieu.pk] = self._parse_field_rows(
                    chi_tieu
                )

        for line in self.indicators:
            chi_tieu = line.chi_tieu
            total = values[chi_tieu.pk]
            bound = self._bound_error(chi_tieu, total)
            if bound:
                self.add_error(f"gia_tri_{chi_tieu.pk}", bound)
            if chi_tieu.phan_loai_doi_tuong:
                self._clean_object_split(chi_tieu, total, cleaned)
            if chi_tieu.phan_loai_linh_vuc:
                self._clean_linh_vuc_split(chi_tieu, total)
            if chi_tieu.khong_vuot_chi_tieu_id:
                self._clean_cap(chi_tieu, total, values)

        return cleaned

    def _bound_error(self, chi_tieu, value):
        """Return the indicator's own bound message, or ``None`` when valid."""
        if value is None:
            return None
        low = chi_tieu.gia_tri_toi_thieu
        high = chi_tieu.gia_tri_toi_da
        if low is None and high is None:
            return None
        if low is not None and high is not None:
            if low <= value <= high:
                return None
            return (
                f"Giá trị phải từ {_format_bound(low)} đến "
                f"{_format_bound(high)}."
            )
        if low is not None:
            if value >= low:
                return None
            return f"Giá trị phải từ {_format_bound(low)}."
        if value <= high:
            return None
        return f"Giá trị không được vượt quá {_format_bound(high)}."

    def _clean_object_split(self, chi_tieu, total, cleaned):
        parts = []
        for doi_tuong in self.object_options[chi_tieu.pk]:
            value = cleaned.get(f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}")
            if value is not None:
                bound = self._bound_error(chi_tieu, value)
                if bound:
                    self.add_error(
                        f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}",
                        bound,
                    )
                parts.append((doi_tuong, value))
        if not parts:
            return
        if total is None:
            self.add_error(
                f"gia_tri_{chi_tieu.pk}",
                (
                    "Tổng chỉ tiêu đang trống nhưng đã có số liệu phân loại "
                    "đối tượng."
                ),
            )
            return
        part_sum = sum((value for _obj, value in parts), ZERO)
        if part_sum != total:
            difference = total - part_sum
            self.add_error(
                f"gia_tri_{chi_tieu.pk}",
                (
                    f"Tổng theo đối tượng là {part_sum}; tổng chỉ tiêu là "
                    f"{total}; lệch {difference}."
                ),
            )

    def _clean_linh_vuc_split(self, chi_tieu, total):
        rows = self.parsed_field_rows.get(chi_tieu.pk, [])
        if not rows:
            return
        if any(row["error"] for row in rows):
            self.add_error(
                f"linh_vuc_grid_{chi_tieu.pk}",
                "Có dòng phân loại lĩnh vực chưa hợp lệ.",
            )
            return
        if total is None:
            self.add_error(
                f"gia_tri_{chi_tieu.pk}",
                (
                    "Tổng chỉ tiêu đang trống nhưng đã có số liệu phân loại "
                    "lĩnh vực."
                ),
            )
            return
        groups = {}
        for row in rows:
            linh_vuc = self.linh_vuc_map.get(row["linh_vuc_id"])
            if linh_vuc is None:
                continue
            groups.setdefault(linh_vuc.he_thong, []).append(row)
        system_labels = dict(HeThongLinhVuc.choices)
        for system, group_rows in groups.items():
            part_sum = sum((row["value"] for row in group_rows), ZERO)
            if part_sum != total:
                difference = total - part_sum
                label = system_labels.get(system, system)
                self.add_error(
                    f"gia_tri_{chi_tieu.pk}",
                    (
                        f"Tổng theo lĩnh vực {label} là {part_sum}; tổng chỉ "
                        f"tiêu là {total}; lệch {difference}."
                    ),
                )

    def _clean_cap(self, chi_tieu, total, values):
        if total is None:
            return
        limit_id = chi_tieu.khong_vuot_chi_tieu_id
        if any(line.chi_tieu.pk == limit_id for line in self.indicators):
            limit = values.get(limit_id)
        else:
            existing = self.existing.get((limit_id, None, None))
            limit = existing.gia_tri if existing is not None else None
        if limit is not None and total > limit:
            self.add_error(
                f"gia_tri_{chi_tieu.pk}",
                (
                    f"Giá trị {total} vượt quá chỉ tiêu "
                    f"{chi_tieu.khong_vuot_chi_tieu.ten_chi_tieu} ({limit})."
                ),
            )

    def _parse_field_rows(self, chi_tieu):
        linh_vuc_ids = self.data.getlist(f"linh_vuc_{chi_tieu.pk}")
        raw_values = self.data.getlist(f"gia_tri_lv_{chi_tieu.pk}")
        posted_ids = []
        for raw_id in linh_vuc_ids:
            raw_id = (raw_id or "").strip()
            if raw_id.isdigit():
                posted_ids.append(int(raw_id))
        missing = [pk for pk in posted_ids if pk not in self.linh_vuc_map]
        if missing:
            for linh_vuc in DanhMucLinhVuc.objects.filter(pk__in=missing):
                self.linh_vuc_map[linh_vuc.pk] = linh_vuc
        rows = []
        seen = set()
        for index, raw_id in enumerate(linh_vuc_ids):
            raw_id = (raw_id or "").strip()
            raw_value = (
                raw_values[index] if index < len(raw_values) else ""
            )
            raw_value = (raw_value or "").strip()
            if not raw_id and not raw_value:
                continue
            row = {
                "linh_vuc_id": None,
                "raw_value": raw_value,
                "value": None,
                "error": "",
            }
            if not raw_id:
                row["error"] = "Chọn lĩnh vực cho dòng có giá trị."
            elif not raw_id.isdigit():
                row["error"] = "Lĩnh vực không hợp lệ."
            else:
                linh_vuc_id = int(raw_id)
                linh_vuc = self.linh_vuc_map.get(linh_vuc_id)
                if linh_vuc is None:
                    row["error"] = "Lĩnh vực không hợp lệ."
                elif linh_vuc_id in seen:
                    row["linh_vuc_id"] = linh_vuc_id
                    row["error"] = (
                        "Lĩnh vực bị chọn trùng trong cùng chỉ tiêu."
                    )
                else:
                    seen.add(linh_vuc_id)
                    row["linh_vuc_id"] = linh_vuc_id
            if raw_value:
                try:
                    value = Decimal(raw_value)
                except InvalidOperation:
                    row["error"] = "Nhập một số hợp lệ."
                else:
                    if value < ZERO:
                        row["error"] = "Giá trị không được âm."
                    else:
                        bound = self._bound_error(chi_tieu, value)
                        if bound:
                            row["error"] = bound
                        else:
                            row["value"] = value
            elif not row["error"]:
                row["error"] = "Nhập giá trị cho lĩnh vực đã chọn."
            if row["error"]:
                self.lv_errors[(chi_tieu.pk, index)] = row["error"]
            rows.append(row)
        return rows

    def validate_required(self):
        """Enforce ``bat_buoc`` rows when a phiếu is submitted.

        M5-T02 must call this after ``is_valid()`` and before setting
        ``trang_thai = cho_duyet``.  Draft saving in M4 never calls it.
        """
        errors = {}
        for line in self.indicators:
            if not line.bat_buoc:
                continue
            field_name = f"gia_tri_{line.chi_tieu.pk}"
            if self.cleaned_data.get(field_name) is None:
                errors[field_name] = (
                    "Chỉ tiêu này là bắt buộc khi gửi duyệt."
                )
        if errors:
            raise ValidationError(errors)

    # ------------------------------------------------------------------
    # Persistence
    # ------------------------------------------------------------------
    @transaction.atomic
    def save(self, phieu):
        """Replace this phiếu's rows for every indicator shown on the form."""
        for line in self.indicators:
            chi_tieu = line.chi_tieu
            total = self.cleaned_data.get(f"gia_tri_{chi_tieu.pk}")
            source = self.cleaned_data.get(f"nguon_{chi_tieu.pk}")
            total_filter = {
                "phieu": phieu,
                "chi_tieu": chi_tieu,
                "doi_tuong": None,
                "linh_vuc": None,
            }
            if total is None and source is None:
                SoLieu.objects.filter(**total_filter).delete()
            else:
                SoLieu.objects.update_or_create(
                    defaults={"gia_tri": total, "nguon": source},
                    **total_filter,
                )

            if chi_tieu.phan_loai_doi_tuong:
                submitted = {}
                for doi_tuong in self.object_options[chi_tieu.pk]:
                    value = self.cleaned_data.get(
                        f"doi_tuong_{chi_tieu.pk}_{doi_tuong.pk}"
                    )
                    if value is not None:
                        submitted[doi_tuong.pk] = value
                for doi_tuong_id, value in submitted.items():
                    SoLieu.objects.update_or_create(
                        phieu=phieu,
                        chi_tieu=chi_tieu,
                        doi_tuong_id=doi_tuong_id,
                        linh_vuc=None,
                        defaults={"gia_tri": value, "nguon": None},
                    )
                SoLieu.objects.filter(
                    phieu=phieu,
                    chi_tieu=chi_tieu,
                    doi_tuong__isnull=False,
                ).exclude(doi_tuong_id__in=submitted).delete()

            if chi_tieu.phan_loai_linh_vuc:
                submitted = {
                    row["linh_vuc_id"]: row["value"]
                    for row in self.parsed_field_rows.get(chi_tieu.pk, [])
                    if row["value"] is not None and not row["error"]
                }
                for linh_vuc_id, value in submitted.items():
                    SoLieu.objects.update_or_create(
                        phieu=phieu,
                        chi_tieu=chi_tieu,
                        doi_tuong=None,
                        linh_vuc_id=linh_vuc_id,
                        defaults={"gia_tri": value, "nguon": None},
                    )
                SoLieu.objects.filter(
                    phieu=phieu,
                    chi_tieu=chi_tieu,
                    linh_vuc__isnull=False,
                ).exclude(linh_vuc_id__in=submitted).delete()


class ActivityEntryForm(IndicatorEntryForm):
    """Activity result form built from active ``BieuMauChiTieu`` rows."""

    def __init__(self, *args, activity, **kwargs):
        self.activity = activity
        bieu_mau = (
            BieuMauChiTieu.objects.filter(
                loai_hoat_dong=activity.loai_hoat_dong,
                chi_tieu__dang_su_dung=True,
            )
            .select_related("chi_tieu", "chi_tieu__nhom")
            .prefetch_related(
                "chi_tieu__nguon_cho_phep",
                "chi_tieu__doi_tuong_ap_dung",
            )
            .order_by("thu_tu", "id")
        )
        indicators = [
            IndicatorLine(chi_tieu=row.chi_tieu, bat_buoc=row.bat_buoc)
            for row in bieu_mau
        ]
        super().__init__(*args, indicators=indicators, **kwargs)


class MonthlyEntryForm(IndicatorEntryForm):
    """Monthly form for one department and one reporting period."""

    def __init__(
        self,
        *args,
        phong,
        ky,
        previous_values=None,
        cumulative_values=None,
        **kwargs,
    ):
        self.phong = phong
        self.ky = ky
        self.previous_values = previous_values or {}
        self.cumulative_values = cumulative_values or {}
        indicators = (
            ChiTieu.objects.filter(
                nhom__phong=phong,
                kieu_ghi_nhan=KieuGhiNhan.MONTH,
                dang_su_dung=True,
            )
            .exclude(
                cach_tong_hop__in=(CachTongHop.RATIO, CachTongHop.COUNT)
            )
            .select_related("nhom")
            .prefetch_related(
                "nguon_cho_phep",
                "doi_tuong_ap_dung",
            )
            .order_by("nhom__thu_tu", "ma_chi_tieu")
        )
        super().__init__(
            *args,
            indicators=[IndicatorLine(chi_tieu=ct) for ct in indicators],
            **kwargs,
        )


class AdHocForm(forms.ModelForm):
    """Text-only form for a "Nhiệm vụ phát sinh" phiếu."""

    class Meta:
        model = HoatDong
        fields = ("noi_dung", "ket_qua")
        labels = {
            "noi_dung": "Nội dung",
            "ket_qua": "Kết quả",
        }
        widgets = {
            "noi_dung": forms.Textarea(attrs={"rows": 4}),
            "ket_qua": forms.Textarea(attrs={"rows": 4}),
        }


class HoTroDuAnForm(forms.ModelForm):
    """One project support line on a project phiếu."""

    class Meta:
        model = HoTroDuAn
        fields = ("loai_ho_tro", "noi_dung", "so_chuyen_gia", "ngay_ho_tro")
        labels = {
            "loai_ho_tro": "Loại hỗ trợ",
            "noi_dung": "Nội dung",
            "so_chuyen_gia": "Số chuyên gia",
            "ngay_ho_tro": "Ngày hỗ trợ",
        }
        widgets = {
            "noi_dung": forms.Textarea(attrs={"rows": 3}),
            "so_chuyen_gia": forms.NumberInput(
                attrs={"min": "0", "step": "0.01"}
            ),
            "ngay_ho_tro": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"type": "date"},
            ),
        }
        error_messages = {
            "loai_ho_tro": {"required": "Chọn loại hỗ trợ."},
            "noi_dung": {"required": "Nhập nội dung hỗ trợ."},
            "ngay_ho_tro": {"required": "Nhập ngày hỗ trợ."},
        }

    def __init__(self, *args, du_an, phieu, **kwargs):
        self.du_an = du_an
        self.phieu = phieu
        super().__init__(*args, **kwargs)
        self.fields["ngay_ho_tro"].input_formats = ["%Y-%m-%d"]
        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("ngay_ho_tro", timezone.localdate())

    def clean_so_chuyen_gia(self):
        value = self.cleaned_data.get("so_chuyen_gia")
        if value is not None and value < ZERO:
            raise forms.ValidationError("Số chuyên gia không được âm.")
        return value

    def save(self, commit=True):
        line = super().save(commit=False)
        line.du_an = self.du_an
        line.phieu = self.phieu
        if commit:
            line.save()
        return line


class WorkflowCommentForm(forms.Form):
    """Comment required when a department head returns or reopens a phiếu."""

    y_kien = forms.CharField(
        label="Ý kiến",
        required=True,
        widget=forms.Textarea(attrs={"rows": 3}),
        error_messages={
            "required": "Vui lòng nhập ý kiến khi trả lại hoặc mở lại phiếu."
        },
    )

    def clean_y_kien(self):
        value = (self.cleaned_data.get("y_kien") or "").strip()
        if not value:
            raise forms.ValidationError(
                "Vui lòng nhập ý kiến khi trả lại hoặc mở lại phiếu."
            )
        return value
