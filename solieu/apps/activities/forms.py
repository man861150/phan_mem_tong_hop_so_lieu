"""Activity types, activities, partner units, and projects."""

from django import forms
from django.utils import timezone

from apps.accounts.scoping import scoped
from apps.activities.models import (
    AD_HOC_ACTIVITY_TYPE_NAME,
    DonViPhoiHop,
    DuAn,
    HoatDong,
)
from apps.catalog.models import PhongBan


class ActivityTypeSelect(forms.Select):
    def create_option(self, name, value, label, selected, index, subindex=None, attrs=None):
        option = super().create_option(
            name,
            value,
            label,
            selected,
            index,
            subindex=subindex,
            attrs=attrs,
        )
        if str(label) == AD_HOC_ACTIVITY_TYPE_NAME:
            option["attrs"]["data-ad-hoc"] = "true"
        return option


class HoatDongForm(forms.ModelForm):
    don_vi_phoi_hop = forms.ModelMultipleChoiceField(
        label="Đơn vị phối hợp",
        queryset=DonViPhoiHop.objects.order_by("ten_don_vi", "id"),
        required=False,
        widget=forms.CheckboxSelectMultiple,
    )

    class Meta:
        model = HoatDong
        fields = (
            "loai_hoat_dong",
            "ten",
            "tu_ngay",
            "den_ngay",
            "dia_diem",
            "hinh_thuc",
            "linh_vuc",
            "doi_tuong_huong_toi",
            "noi_dung",
            "ket_qua",
        )
        widgets = {
            "loai_hoat_dong": ActivityTypeSelect(
                attrs={
                    "class": "form-select",
                    "x-ref": "loai",
                    "@change": "syncAdHoc()",
                }
            ),
            "ten": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Ví dụ: Ngày hội kết nối khởi nghiệp",
                }
            ),
            "tu_ngay": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"},
            ),
            "den_ngay": forms.DateInput(
                format="%Y-%m-%d",
                attrs={"class": "form-control", "type": "date"},
            ),
            "dia_diem": forms.TextInput(
                attrs={
                    "class": "form-control",
                    "placeholder": "Nhập địa chỉ hoặc nền tảng tổ chức",
                }
            ),
            "hinh_thuc": forms.Select(attrs={"class": "form-select"}),
            "doi_tuong_huong_toi": forms.CheckboxSelectMultiple,
            "noi_dung": forms.Textarea(
                attrs={"class": "form-control", "rows": 4}
            ),
            "ket_qua": forms.Textarea(attrs={"class": "form-control", "rows": 4}),
        }
        labels = {
            "loai_hoat_dong": "Loại hoạt động",
            "ten": "Tên hoạt động",
            "tu_ngay": "Từ ngày",
            "den_ngay": "Đến ngày",
            "dia_diem": "Địa điểm tổ chức",
            "hinh_thuc": "Hình thức tổ chức",
            "linh_vuc": "Lĩnh vực",
            "doi_tuong_huong_toi": "Đối tượng hướng tới",
            "noi_dung": "Nội dung",
            "ket_qua": "Kết quả",
        }
        error_messages = {
            "loai_hoat_dong": {
                "required": "Chọn loại hoạt động.",
                "invalid_choice": "Loại hoạt động không hợp lệ.",
            },
            "ten": {"required": "Nhập tên hoạt động."},
            "tu_ngay": {
                "required": "Nhập ngày bắt đầu.",
                "invalid": "Nhập ngày bắt đầu hợp lệ (dd/mm/yyyy).",
            },
            "den_ngay": {
                "invalid": "Nhập ngày kết thúc hợp lệ (dd/mm/yyyy).",
            },
            "linh_vuc": {
                "invalid_choice": "Lĩnh vực không hợp lệ.",
            },
            "doi_tuong_huong_toi": {
                "invalid_choice": "Đối tượng hướng tới không hợp lệ.",
            },
        }

    def __init__(self, *args, user=None, **kwargs):
        self.user = user
        super().__init__(*args, **kwargs)
        self.fields["tu_ngay"].input_formats = ["%Y-%m-%d"]
        self.fields["den_ngay"].input_formats = ["%Y-%m-%d"]
        self.fields["den_ngay"].required = False
        self.fields["dia_diem"].required = False
        self.fields["noi_dung"].required = False
        self.fields["ket_qua"].required = False
        self.fields["loai_hoat_dong"].empty_label = "Chọn loại hoạt động"
        self.fields["linh_vuc"].empty_label = "Chọn lĩnh vực"
        self.fields["don_vi_phoi_hop"].error_messages = {
            "invalid_choice": "Đơn vị phối hợp không hợp lệ.",
            "invalid_pk_value": "Đơn vị phối hợp không hợp lệ.",
        }
        self.fields["noi_dung"].help_text = (
            "Bắt buộc với loại Nhiệm vụ phát sinh trước khi chuyển sang Đã tổ chức."
        )
        self.fields["ket_qua"].help_text = (
            "Bắt buộc với loại Nhiệm vụ phát sinh trước khi chuyển sang Đã tổ chức."
        )

        phong_id = None
        if self.instance.pk:
            phong_id = self.instance.loai_hoat_dong.phong_id
        elif user is not None:
            phong_id = getattr(user, "phong_id", None)
        self.fields["loai_hoat_dong"].queryset = (
            self.fields["loai_hoat_dong"]
            .queryset.filter(phong_id=phong_id)
            .select_related("phong")
            .order_by("ten_loai")
        )
        self.fields["linh_vuc"].queryset = (
            self.fields["linh_vuc"]
            .queryset.select_related("cha")
            .order_by("he_thong", "ma")
        )
        self.fields["doi_tuong_huong_toi"].queryset = (
            self.fields["doi_tuong_huong_toi"]
            .queryset.order_by("ten_doi_tuong")
        )

        if self.instance.pk:
            self.fields["don_vi_phoi_hop"].initial = list(
                self.instance.don_vi_tham_gia.values_list("don_vi_id", flat=True)
            )

    def save(self, commit=True):
        hoat_dong = super().save(commit=commit)
        if commit:
            self._save_don_vi(hoat_dong)
        return hoat_dong

    def _save_don_vi(self, hoat_dong):
        selected = {row.pk: row for row in self.cleaned_data["don_vi_phoi_hop"]}
        existing = {
            row.don_vi_id: row
            for row in hoat_dong.don_vi_tham_gia.select_related("don_vi")
        }
        hoat_dong.don_vi_tham_gia.filter(
            don_vi_id__in=[pk for pk in existing if pk not in selected]
        ).delete()
        for don_vi_id in selected:
            if don_vi_id not in existing:
                hoat_dong.don_vi_tham_gia.create(
                    don_vi_id=don_vi_id,
                    vai_tro="Phối hợp",
                )


class DuAnForm(forms.ModelForm):
    class Meta:
        model = DuAn
        fields = ("phong", "ten_du_an", "chuong_trinh", "hinh_thuc", "nam")
        widgets = {
            "nam": forms.NumberInput(attrs={"min": 2000, "max": 2100}),
        }
        labels = {
            "phong": "Phòng ban",
            "ten_du_an": "Tên dự án",
            "chuong_trinh": "Chương trình",
            "hinh_thuc": "Hình thức",
            "nam": "Năm",
        }
        error_messages = {
            "phong": {"required": "Chọn phòng ban."},
            "ten_du_an": {"required": "Nhập tên dự án."},
            "chuong_trinh": {"required": "Chọn chương trình."},
            "hinh_thuc": {"required": "Chọn hình thức."},
            "nam": {"required": "Nhập năm."},
        }

    def __init__(self, *args, user=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["phong"].queryset = scoped(
            user,
            PhongBan.objects.all(),
            "id",
        ).order_by("ma_phong")
        if not self.is_bound and not self.instance.pk:
            self.initial.setdefault("nam", timezone.localdate().year)
