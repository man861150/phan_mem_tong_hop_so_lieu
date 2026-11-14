"""Designer forms and the dynamic entry form.

Posted custom names are the field key (`cf_...`). Core widgets stay on the
existing entry forms. This form only validates and stores custom fields.
"""

from django import forms
from django.core.exceptions import ValidationError

from apps.formbuilder.models import (
    FieldType,
    FormValue,
    FunctionType,
)
from apps.formbuilder.values import (
    BOOL_TYPES,
    FILE_TYPES,
    echo_raw,
    evaluate_rules,
    is_empty,
    parse_posted,
    save_entries,
    widget_value,
)

SPAN_CLASSES = {index: f"form-span-{index}" for index in range(1, 13)}


class TemplateCreateForm(forms.Form):
    name = forms.CharField(label="Tên biểu mẫu", max_length=255)
    function_type = forms.ChoiceField(label="Chức năng", choices=FunctionType.choices)
    target = forms.ChoiceField(label="Phạm vi", required=False)
    description = forms.CharField(
        label="Mô tả",
        required=False,
        widget=forms.Textarea(attrs={"rows": 3}),
    )

    def __init__(self, *args, targets=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["target"].choices = [("", "Tất cả")] + list(targets or [])


class TemplateMetaForm(forms.Form):
    name = forms.CharField(label="Tên biểu mẫu", max_length=255)
    description = forms.CharField(label="Mô tả", required=False, widget=forms.Textarea)
    layout_notes = forms.CharField(
        label="Ghi chú nội bộ",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )


class SectionForm(forms.Form):
    title = forms.CharField(label="Tiêu đề", max_length=255)
    description = forms.CharField(label="Mô tả", required=False, widget=forms.Textarea)
    columns = forms.IntegerField(label="Số cột", min_value=1, max_value=4)
    is_collapsible = forms.BooleanField(label="Cho phép thu gọn", required=False)
    is_collapsed = forms.BooleanField(label="Thu gọn ban đầu", required=False)


class FieldUpdateForm(forms.Form):
    label = forms.CharField(label="Nhãn", max_length=255)
    required = forms.BooleanField(label="Bắt buộc", required=False)
    read_only = forms.BooleanField(label="Chỉ đọc", required=False)
    placeholder = forms.CharField(label="Gợi ý nhập", required=False, max_length=255)
    help_text = forms.CharField(
        label="Trợ giúp",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    default_value = forms.CharField(
        label="Giá trị mặc định",
        required=False,
        widget=forms.Textarea(attrs={"rows": 2}),
    )
    col_span = forms.IntegerField(label="Độ rộng", min_value=1, max_value=12)
    is_hidden_by_default = forms.BooleanField(label="Ẩn mặc định", required=False)
    is_per_row = forms.BooleanField(label="Theo từng dòng", required=False)
    min_value = forms.DecimalField(
        label="Giá trị nhỏ nhất",
        required=False,
        max_digits=18,
        decimal_places=4,
    )
    max_value = forms.DecimalField(
        label="Giá trị lớn nhất",
        required=False,
        max_digits=18,
        decimal_places=4,
    )
    min_length = forms.IntegerField(
        label="Độ dài nhỏ nhất", required=False, min_value=0
    )
    max_length = forms.IntegerField(
        label="Độ dài lớn nhất", required=False, min_value=0
    )
    regex = forms.CharField(label="Biểu thức", required=False, max_length=255)
    max_file_size_mb = forms.IntegerField(
        label="Dung lượng tối đa (MB)",
        required=False,
        min_value=1,
        max_value=25,
    )
    allowed_extensions = forms.CharField(
        label="Phần mở rộng",
        required=False,
        max_length=255,
    )
    unique_within_form = forms.BooleanField(
        label="Không trùng trong biểu mẫu",
        required=False,
    )
    catalog_source = forms.ChoiceField(label="Danh mục", required=False)
    section = forms.ModelChoiceField(label="Phần", queryset=None)

    def __init__(self, *args, sections=None, catalog_choices=None, **kwargs):
        super().__init__(*args, **kwargs)
        self.fields["section"].queryset = sections
        self.fields["catalog_source"].choices = [("", "—")] + list(
            catalog_choices or []
        )


class OptionForm(forms.Form):
    label = forms.CharField(label="Nhãn", max_length=255)
    value = forms.CharField(label="Giá trị", max_length=100, required=False)


class RuleForm(forms.Form):
    source_field_key = forms.ChoiceField(label="Khi trường")
    operator = forms.ChoiceField(label="Phép so sánh")
    compare_value = forms.CharField(label="Giá trị", required=False)
    action = forms.ChoiceField(label="Thì")
    target_field_key = forms.ChoiceField(label="Trường")

    def __init__(self, *args, field_choices=None, **kwargs):
        from apps.formbuilder.models import RuleAction, RuleOperator

        super().__init__(*args, **kwargs)
        self.fields["source_field_key"].choices = field_choices or []
        self.fields["target_field_key"].choices = field_choices or []
        self.fields["operator"].choices = RuleOperator.choices
        self.fields["action"].choices = RuleAction.choices


def _version_fields(version):
    fields = []
    for section in version.sections.all():
        fields.extend(list(section.fields.all()))
    return fields


def _input_widget(field):
    css = "form-control"
    if field.field_type == FieldType.TEXTAREA:
        return forms.Textarea(attrs={"rows": 3, "class": css})
    if field.field_type in {"integer", "decimal", "percent"}:
        step = "1" if field.field_type == FieldType.INTEGER else "0.01"
        return forms.NumberInput(attrs={"class": css, "step": step})
    if field.field_type == FieldType.DATE:
        return forms.DateInput(attrs={"type": "date", "class": css})
    if field.field_type == FieldType.TIME:
        return forms.TimeInput(attrs={"type": "time", "class": css})
    if field.field_type == FieldType.DATETIME:
        return forms.DateTimeInput(attrs={"type": "datetime-local", "class": css})
    if field.field_type == FieldType.SELECT:
        return forms.Select(attrs={"class": css})
    if field.field_type == FieldType.RADIO:
        return forms.RadioSelect()
    if field.field_type == FieldType.MULTI_SELECT:
        return forms.CheckboxSelectMultiple()
    if field.field_type in BOOL_TYPES or field.field_type in FILE_TYPES:
        return (
            forms.ClearableFileInput()
            if field.field_type in FILE_TYPES
            else forms.CheckboxInput()
        )
    if field.field_type == FieldType.EMAIL:
        return forms.EmailInput(attrs={"class": css})
    if field.field_type == FieldType.PHONE:
        return forms.TextInput(attrs={"class": css, "type": "tel"})
    if field.field_type == FieldType.URL:
        return forms.URLInput(attrs={"class": css})
    return forms.TextInput(attrs={"class": css, "placeholder": field.placeholder})


def _choice_pairs(field):
    pairs = [
        (option.value, option.label)
        for option in field.options.all()
        if option.is_active
    ]
    return pairs


class DynamicEntryForm(forms.Form):
    """Custom fields for one template version.

    ``mode="form"`` is one value per phiếu. ``mode="row"`` repeats each
    per-row field once per indicator id. Required checks run only when
    ``enforce_required`` is true. Type checks always run for visible values.
    """

    def __init__(
        self,
        data=None,
        files=None,
        *,
        version,
        phieu,
        enforce_required=False,
        mode="form",
        indicator_ids=None,
        extra_values=None,
    ):
        super().__init__(data, files)
        self.version = version
        self.phieu = phieu
        self.enforce_required = enforce_required
        self.mode = mode
        self.indicator_ids = list(indicator_ids or [])
        self.extra_values = dict(extra_values or {})
        self.custom_fields = []
        self.bound_names = {}
        self.value_map = {}
        self.visible = {}
        self.required_map = {}
        self.entries = []
        fields = _version_fields(version)
        selected = [
            field
            for field in fields
            if field.source == "custom"
            and field.field_type != FieldType.INSTRUCTION
            and field.is_per_row == (mode == "row")
        ]
        self.custom_fields = selected
        targets = self.indicator_ids if mode == "row" else [None]
        for field in selected:
            for indicator_id in targets:
                name = (
                    field.key
                    if indicator_id is None
                    else f"{field.key}__ct_{indicator_id}"
                )
                self.bound_names[name] = (field, indicator_id)
                self.fields[name] = self._build(field, name)
        self._apply_initial()

    def _build(self, field, name):
        common = {
            "label": field.label,
            "required": False,
            "help_text": field.help_text,
        }
        if field.field_type == FieldType.SELECT:
            return forms.ChoiceField(
                choices=[("", "—")] + _choice_pairs(field),
                widget=_input_widget(field),
                **common,
            )
        if field.field_type == FieldType.RADIO:
            return forms.ChoiceField(
                choices=_choice_pairs(field),
                widget=forms.RadioSelect(),
                **common,
            )
        if field.field_type == FieldType.MULTI_SELECT:
            return forms.MultipleChoiceField(
                choices=_choice_pairs(field),
                widget=forms.CheckboxSelectMultiple(),
                **common,
            )
        if field.field_type == FieldType.LOOKUP:
            from apps.formbuilder.lookups import lookup_choices

            choices = lookup_choices(
                field.catalog_source, self.version.template.phong_id
            )
            return forms.ChoiceField(
                choices=[("", "—")] + choices,
                widget=_input_widget(field),
                **common,
            )
        if field.field_type in FILE_TYPES:
            return forms.FileField(widget=_input_widget(field), **common)
        if field.field_type in BOOL_TYPES:
            return forms.BooleanField(widget=forms.CheckboxInput(), **common)
        return forms.CharField(widget=_input_widget(field), **common)

    def _apply_initial(self):
        if self.is_bound or self.phieu is None or not self.phieu.pk:
            return
        response = self.phieu.form_responses.filter(
            template=self.version.template
        ).first()
        if response is None:
            for name, (field, _indicator_id) in self.bound_names.items():
                if field.default_value:
                    self.initial[name] = field.default_value
            return
        stored = {
            (row.field_key, row.so_lieu.chi_tieu_id if row.so_lieu_id else None): row
            for row in response.values.select_related("so_lieu")
        }
        for name, (field, indicator_id) in self.bound_names.items():
            row = stored.get((field.key, indicator_id))
            if row is None:
                if field.default_value and field.field_type not in FILE_TYPES:
                    self.initial[name] = field.default_value
                continue
            from apps.formbuilder.values import _stored_python

            self.initial[name] = widget_value(field, _stored_python(row))

    def _posted(self, name, field):
        if field.field_type == FieldType.MULTI_SELECT:
            return (
                self.data.getlist(name)
                if hasattr(self.data, "getlist")
                else self.data.get(name)
            )
        if field.field_type in FILE_TYPES:
            return self.files.get(name)
        if field.field_type in BOOL_TYPES:
            return name in self.data
        return self.data.get(name, "")

    def _existing_file(self, field, indicator_id):
        if self.phieu is None or not self.phieu.pk:
            return False
        lookup = {
            "response__phieu": self.phieu,
            "response__template": self.version.template,
            "field_key": field.key,
            "attachments__isnull": False,
        }
        if indicator_id is None:
            lookup["so_lieu__isnull"] = True
        else:
            lookup["so_lieu__chi_tieu_id"] = indicator_id
        return FormValue.objects.filter(**lookup).exists()

    def _duplicate(self, field, parsed, indicator_id, seen):
        if not field.unique_within_form or is_empty(parsed):
            return False
        marker = (field.key, str(parsed))
        if marker in seen:
            return True
        seen.add(marker)
        column = "value_text"
        stored = parsed
        if field.field_type in {"integer", "decimal", "percent"}:
            column = "value_number"
        elif field.field_type == FieldType.DATE:
            column = "value_date"
        elif field.field_type == FieldType.MULTI_SELECT:
            column = "value_json"
        elif field.field_type in BOOL_TYPES:
            column = "value_bool"
        queryset = FormValue.objects.filter(
            field__key=field.key,
            response__template=self.version.template,
            **{column: stored},
        )
        if self.phieu is not None and self.phieu.pk:
            queryset = queryset.exclude(response__phieu=self.phieu)
        if indicator_id is not None:
            queryset = queryset.exclude(so_lieu__chi_tieu_id=indicator_id)
        return queryset.exists()

    def clean(self):
        cleaned = super().clean()
        fields = _version_fields(self.version)
        base_values = {}
        if self.phieu is not None:
            for field in fields:
                if field.source == "core":
                    base_values[field.key] = echo_raw(self.phieu, field.core_key)
        base_values.update(self.extra_values)
        posted = {}
        for name, (field, indicator_id) in self.bound_names.items():
            if indicator_id is None:
                posted[field.key] = self._posted(name, field)
        visible, required = evaluate_rules(
            fields,
            list(self.version.rules.all()),
            {**base_values, **posted, **self.extra_values},
        )
        self.visible = visible
        self.required_map = required
        self.entries = []
        seen = set()
        phong_id = self.version.template.phong_id
        for name, (field, indicator_id) in self.bound_names.items():
            if not visible.get(field.key, True):
                self._errors.pop(name, None)
                cleaned.pop(name, None)
                continue
            raw = self._posted(name, field)
            upload = raw if field.field_type in FILE_TYPES else None
            try:
                parsed = parse_posted(
                    field,
                    None if field.field_type in FILE_TYPES else raw,
                    upload,
                    phong_id=phong_id,
                )
            except ValidationError as exc:
                self.add_error(name, exc)
                continue
            if (
                is_empty(parsed)
                and field.default_value
                and not self._has_stored(field, indicator_id)
                and field.field_type not in FILE_TYPES | BOOL_TYPES
            ):
                try:
                    parsed = parse_posted(
                        field,
                        field.default_value,
                        None,
                        phong_id=phong_id,
                    )
                except ValidationError as exc:
                    self.add_error(name, exc)
                    continue
            if self.enforce_required and required.get(field.key, False):
                missing = parsed is None or parsed == [] or parsed is False
                if field.field_type in FILE_TYPES and self._existing_file(
                    field, indicator_id
                ):
                    missing = upload in (None, False) and not self._existing_file(
                        field,
                        indicator_id,
                    )
                if missing:
                    self.add_error(name, f"Vui lòng nhập {field.label}.")
                    continue
            if self._duplicate(field, parsed, indicator_id, seen):
                self.add_error(name, f"{field.label} bị trùng trong biểu mẫu.")
                continue
            cleaned[name] = parsed
            self.value_map[field.key] = parsed
            self.entries.append(
                {
                    "field": field,
                    "parsed": parsed,
                    "upload": upload if field.field_type in FILE_TYPES else None,
                    "indicator_id": indicator_id,
                    "name": name,
                }
            )
        return cleaned

    def _has_stored(self, field, indicator_id):
        if self.phieu is None or not self.phieu.pk:
            return False
        lookup = {
            "response__phieu": self.phieu,
            "response__template": self.version.template,
            "field_key": field.key,
        }
        if indicator_id is None:
            lookup["so_lieu__isnull"] = True
        else:
            lookup["so_lieu__chi_tieu_id"] = indicator_id
        return FormValue.objects.filter(**lookup).exists()

    def save(self, phieu, user):
        from apps.entry.models import SoLieu

        payload = []
        for entry in self.entries:
            so_lieu = None
            indicator_id = entry["indicator_id"]
            if indicator_id is not None:
                so_lieu = SoLieu.objects.filter(
                    phieu=phieu,
                    chi_tieu_id=indicator_id,
                    doi_tuong=None,
                    linh_vuc=None,
                ).first()
                filled = entry["parsed"] not in (None, [], False)
                if so_lieu is None and (filled or self.enforce_required):
                    if filled or self.required_map.get(entry["field"].key):
                        raise ValidationError(
                            "Hãy nhập giá trị chỉ tiêu trước khi nhập "
                            f"{entry['field'].label}."
                        )
                if so_lieu is None:
                    continue
            payload.append(
                {
                    "field": entry["field"],
                    "parsed": entry["parsed"],
                    "upload": entry["upload"],
                    "so_lieu": so_lieu,
                }
            )
        return save_entries(phieu, self.version, user, payload)

    def error_messages(self):
        messages = []
        for name, errors in self.errors.items():
            field = self.fields.get(name)
            label = field.label if field is not None else ""
            for message in errors:
                text = str(message)
                if (
                    label
                    and not text.startswith(label)
                    and not text.startswith("Vui lòng")
                ):
                    text = f"{label}: {text}"
                messages.append(text)
        return messages
