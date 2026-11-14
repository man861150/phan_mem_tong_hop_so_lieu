"""Bind a published template onto an existing phiếu without replacing it."""

from django.http import QueryDict

from apps.formbuilder.forms import SPAN_CLASSES, DynamicEntryForm, _version_fields
from apps.formbuilder.models import FormResponse
from apps.formbuilder.services import (
    load_version,
    resolve_form_template,
    resolve_row_template,
)
from apps.formbuilder.values import (
    echo_raw,
    echo_text,
    evaluate_rules,
    render_readonly,
)


class EntryBundle:
    """Form-level custom fields plus per-row fields for indicator grids."""

    def __init__(self, phieu, form=None, row_forms=None):
        self.phieu = phieu
        self.form = form
        self.row_forms = list(row_forms or [])

    def is_valid(self):
        ok = True
        extra = {}
        if self.form is not None:
            if not self.form.is_valid():
                ok = False
            extra = dict(self.form.value_map)
        for row_form in self.row_forms:
            row_form.extra_values = extra
            if not row_form.is_valid():
                ok = False
        return ok

    def save(self, phieu, user):
        if self.form is not None:
            self.form.save(phieu, user)
        for row_form in self.row_forms:
            row_form.save(phieu, user)

    @property
    def errors(self):
        """Bound-field errors. Empty until ``is_valid()`` runs."""
        found = []
        forms = [self.form] if self.form is not None else []
        forms.extend(self.row_forms)
        for form in forms:
            if not form.is_bound:
                continue
            for messages in form.errors.values():
                found.extend(messages)
        return found

    def error_messages(self):
        messages = []
        if self.form is not None:
            messages.extend(self.form.error_messages())
        for row_form in self.row_forms:
            messages.extend(row_form.error_messages())
        return messages

    def fields_for_indicator(self, indicator_id):
        found = []
        for row_form in self.row_forms:
            for name, (field, target_id) in row_form.bound_names.items():
                if target_id != indicator_id:
                    continue
                bound = row_form[name]
                found.append(
                    {
                        "label": field.label,
                        "help_text": field.help_text,
                        "required": row_form.required_map.get(
                            field.key, field.required
                        ),
                        "bound": bound,
                        "errors": bound.errors,
                        "key": field.key,
                    }
                )
        return found


def _targets_from_rows(rows):
    targets = []
    for row in rows or []:
        indicator = row.get("chi_tieu")
        if indicator is None:
            continue
        targets.append((indicator.pk, indicator.nhom_id))
    return targets


def bind_entry(phieu, data, files, *, enforce_required, rows=None):
    """Return an EntryBundle, or None when no published template applies."""
    if phieu is None:
        return None
    form = None
    version = resolve_form_template(phieu)
    if version is not None:
        loaded = load_version(version)
        form = DynamicEntryForm(
            data,
            files,
            version=loaded,
            phieu=phieu,
            enforce_required=enforce_required,
        )
    grouped = {}
    for indicator_id, group_id in _targets_from_rows(rows):
        row_version = resolve_row_template(phieu, group_id)
        if row_version is None:
            continue
        bucket = grouped.setdefault(row_version.pk, [row_version, []])
        bucket[1].append(indicator_id)
    row_forms = []
    for row_version, indicator_ids in grouped.values():
        row_forms.append(
            DynamicEntryForm(
                data,
                files,
                version=load_version(row_version),
                phieu=phieu,
                enforce_required=enforce_required,
                mode="row",
                indicator_ids=indicator_ids,
            )
        )
    if form is None and not row_forms:
        return None
    return EntryBundle(phieu, form, row_forms)


def _visibility(version, phieu, form):
    if form is not None and form.is_bound:
        return form.visible, form.required_map
    fields = _version_fields(version)
    values = {}
    for field in fields:
        if field.source == "core" and phieu is not None:
            values[field.key] = echo_raw(phieu, field.core_key)
    return evaluate_rules(fields, list(version.rules.all()), values)


def layout_sections(bundle, phieu):
    """Sections for the entry template. None when there is nothing to add."""
    if bundle is None or bundle.form is None:
        return None
    version = bundle.form.version
    visible, required = _visibility(version, phieu, bundle.form)
    sections = []
    system_seen = False
    for section in version.sections.all():
        items = []
        for field in section.fields.all():
            if field.is_per_row:
                continue
            if not visible.get(field.key, True):
                continue
            span = SPAN_CLASSES.get(field.col_span, "form-span-12")
            if field.source == "core" and get_system(field):
                system_seen = True
                items.append(
                    {"kind": "system", "field": field, "span_class": "form-span-12"}
                )
                continue
            if field.source == "core" and get_grid(field):
                continue
            if field.source == "core":
                items.append(
                    {
                        "kind": "echo",
                        "label": field.label,
                        "value": echo_text(phieu, field.core_key) if phieu else "—",
                        "span_class": span,
                    }
                )
                continue
            if field.field_type == "instruction":
                items.append(
                    {
                        "kind": "instruction",
                        "label": field.label,
                        "help_text": field.help_text,
                        "span_class": span,
                    }
                )
                continue
            bound = bundle.form[field.key] if field.key in bundle.form.fields else None
            if bound is None:
                continue
            items.append(
                {
                    "kind": "input",
                    "label": field.label,
                    "help_text": field.help_text,
                    "required": required.get(field.key, field.required),
                    "bound": bound,
                    "errors": bound.errors,
                    "span_class": span,
                    "key": field.key,
                    "field_type": field.field_type,
                }
            )
        if items or section.description:
            sections.append(
                {
                    "title": section.title,
                    "description": section.description,
                    "columns": section.columns,
                    "collapsible": section.is_collapsible,
                    "collapsed": section.is_collapsed,
                    "items": items,
                }
            )
    return {"sections": sections, "system_seen": system_seen, "version": version}


def get_system(field):
    from apps.formbuilder.core import get_core_field

    definition = get_core_field(field.version.template.function_type, field.core_key)
    return bool(definition and definition.system_block)


def get_grid(field):
    from apps.formbuilder.core import get_core_field

    definition = get_core_field(field.version.template.function_type, field.core_key)
    return bool(definition and definition.grid_column)


def attach_row_fields(rows, bundle):
    if not rows:
        return rows
    for row in rows:
        indicator = row.get("chi_tieu")
        row["custom_fields"] = (
            bundle.fields_for_indicator(indicator.pk)
            if bundle is not None and indicator is not None
            else []
        )
    return rows


def readonly_context(phieu):
    groups = []
    row_values = {}
    responses = phieu.form_responses.select_related("template", "template_version")
    for response in responses:
        rendered = render_readonly(response)
        if rendered["sections"]:
            groups.append(
                {
                    "template": response.template,
                    "version": response.template_version,
                    "sections": rendered["sections"],
                }
            )
        row_values.update(rendered["rows"])
    return {"custom_groups": groups, "custom_row_values": row_values}


def custom_submission_errors(phieu):
    """Vietnamese blockers for gửi duyệt, using the pinned or published version."""
    from apps.entry.forms import ActivityEntryForm, MonthlyEntryForm
    from apps.entry.models import LoaiPhieu

    rows = []
    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        activity = phieu.hoat_dong
        if not activity.la_nhiem_vu_phat_sinh:
            form = ActivityEntryForm(activity=activity, phieu=phieu)
            rows = [{"chi_tieu": line.chi_tieu} for line in form.indicators]
    elif phieu.loai_phieu == LoaiPhieu.THANG and phieu.ky_id:
        form = MonthlyEntryForm(phong=phieu.phong, ky=phieu.ky, phieu=phieu)
        rows = [{"chi_tieu": line.chi_tieu} for line in form.indicators]
    data = _stored_querydict(phieu)
    bundle = bind_entry(phieu, data, None, enforce_required=True, rows=rows)
    if bundle is None:
        return []
    bundle.is_valid()
    return bundle.error_messages()


def _stored_querydict(phieu):
    data = QueryDict(mutable=True)
    responses = FormResponse.objects.filter(phieu=phieu).prefetch_related(
        "values__field",
        "values__so_lieu",
    )
    for response in responses:
        for row in response.values.all():
            name = row.field_key
            if row.so_lieu_id:
                name = f"{row.field_key}__ct_{row.so_lieu.chi_tieu_id}"
            field_type = row.field.field_type
            if field_type == "multi_select":
                data.setlist(name, [str(item) for item in (row.value_json or [])])
            elif field_type in {"checkbox", "switch"}:
                if row.value_bool:
                    data[name] = "on"
            elif (
                field_type in {"integer", "decimal", "percent"}
                and row.value_number is not None
            ):
                data[name] = format(row.value_number, "f")
            elif field_type == "date" and row.value_date:
                data[name] = row.value_date.isoformat()
            elif field_type == "time" and row.value_time:
                data[name] = row.value_time.strftime("%H:%M")
            elif field_type == "datetime" and row.value_datetime:
                data[name] = row.value_datetime.isoformat()
            elif row.value_text:
                data[name] = row.value_text
    return data


def needs_multipart(bundle):
    if bundle is None:
        return False
    forms = [bundle.form, *bundle.row_forms]
    return any(
        form is not None
        and any(field.field_type in {"file", "image"} for field in form.custom_fields)
        for form in forms
    )
