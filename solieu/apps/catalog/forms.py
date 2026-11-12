"""Departments, indicators, annual plans, lookup tables, and form templates."""

from django import forms


class TraLaiKeHoachForm(forms.Form):
    y_kien = forms.CharField(
        label="Ý kiến",
        widget=forms.Textarea(attrs={"rows": 3, "class": "form-control"}),
        error_messages={"required": "Trả lại kế hoạch phải có ý kiến."},
    )
