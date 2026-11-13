"""Aggregation, Excel export, Word export, and published reports."""

from __future__ import annotations

from pathlib import Path

from django import forms

from apps.catalog.models import PhongBan
from apps.reporting.periods import (
    KIND_CHOICES,
    KIND_MONTH,
    resolve_period,
    today,
)

MAX_UPLOAD_BYTES = 5 * 1024 * 1024
UPLOAD_TOO_LARGE = "Tệp vượt quá dung lượng cho phép (5 MB)."


class BaoCaoPeriodForm(forms.Form):
    """Choose a reporting period and a department or the whole center."""

    kind = forms.ChoiceField(
        label="Loại kỳ",
        choices=KIND_CHOICES,
        initial=KIND_MONTH,
        widget=forms.Select(attrs={"class": "form-select"}),
    )
    year = forms.IntegerField(
        label="Năm",
        min_value=2000,
        max_value=2100,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    month = forms.IntegerField(
        label="Tháng",
        min_value=1,
        max_value=12,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    quarter = forms.IntegerField(
        label="Quý",
        min_value=1,
        max_value=4,
        required=False,
        widget=forms.NumberInput(attrs={"class": "form-control"}),
    )
    phong = forms.ModelChoiceField(
        label="Phạm vi",
        queryset=PhongBan.objects.none(),
        required=False,
        empty_label="Toàn trung tâm",
        widget=forms.Select(attrs={"class": "form-select"}),
    )

    def __init__(self, *args, departments=None, **kwargs):
        super().__init__(*args, **kwargs)
        department_ids = (
            [phong.pk for phong in departments]
            if departments is not None
            else []
        )
        self.fields["phong"].queryset = PhongBan.objects.filter(
            pk__in=department_ids
        )
        current = today()
        if not self.is_bound:
            self.fields["year"].initial = current.year
            self.fields["month"].initial = current.month
            self.fields["quarter"].initial = (current.month - 1) // 3 + 1

    def clean(self):
        cleaned = super().clean()
        kind = cleaned.get("kind")
        year = cleaned.get("year")
        if not kind or not year:
            return cleaned
        try:
            self.period = resolve_period(
                kind,
                year,
                month=cleaned.get("month"),
                quarter=cleaned.get("quarter"),
            )
        except ValueError as exc:
            raise forms.ValidationError(str(exc)) from exc
        return cleaned


class XlsxUploadForm(forms.Form):
    file = forms.FileField(
        label="Tệp Excel",
        widget=forms.ClearableFileInput(
            attrs={"class": "form-control", "accept": ".xlsx"}
        ),
    )

    def clean_file(self):
        uploaded = self.cleaned_data["file"]
        if Path(uploaded.name).suffix.lower() != ".xlsx":
            raise forms.ValidationError("Vui lòng chọn tệp có đuôi .xlsx.")
        if uploaded.size > MAX_UPLOAD_BYTES:
            raise forms.ValidationError(UPLOAD_TOO_LARGE)
        return uploaded
