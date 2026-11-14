"""Rule evaluation and normalized storage for custom field values.

Rules run in ``order``. A rule changes visibility or requiredness only when
its single condition matches. A later matching rule replaces the earlier one.
Hidden values are kept and are neither validated nor shown.
"""

from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation

from django.core.exceptions import ValidationError
from django.db import transaction
from django.utils import timezone
from django.utils.dateparse import parse_date, parse_datetime, parse_time

from apps.formbuilder.core import get_core_field
from apps.formbuilder.lookups import resolve_lookup
from apps.formbuilder.models import (
    FieldType,
    FormAttachment,
    FormResponse,
    FormValue,
)
from apps.formbuilder.validators import (
    compile_regex,
    normalize_phone,
    sanitize_filename,
    validate_email_value,
    validate_upload,
    validate_url_value,
)
from apps.reporting.formatting import format_vi_number

TEXT_TYPES = frozenset(
    {"text", "textarea", "select", "radio", "email", "phone", "url", "lookup"}
)
NUMBER_TYPES = frozenset({"integer", "decimal", "percent"})
BOOL_TYPES = frozenset({"checkbox", "switch"})
FILE_TYPES = frozenset({"file", "image"})


def is_empty(value):
    if value is None:
        return True
    if isinstance(value, str) and value.strip() == "":
        return True
    if isinstance(value, (list, tuple)) and len(value) == 0:
        return True
    return False


def _as_text(value):
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (list, tuple)):
        return ",".join(str(item) for item in value)
    if isinstance(value, datetime):
        return value.isoformat(timespec="minutes")
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, time):
        return value.strftime("%H:%M")
    if isinstance(value, Decimal):
        return format(value, "f")
    return str(value).strip()


def _as_decimal(value):
    if isinstance(value, Decimal):
        return value
    text = _as_text(value).replace(",", ".")
    if text == "":
        return None
    try:
        return Decimal(text)
    except InvalidOperation:
        return None


def condition_matches(operator, current, compare):
    """Return whether one rule condition matches. Compare text is already stored."""
    if operator == "is_empty":
        return is_empty(current)
    if operator == "is_not_empty":
        return not is_empty(current)
    if operator == "contains":
        if isinstance(current, (list, tuple)):
            return str(compare).strip() in {str(item) for item in current}
        return str(compare).strip() in _as_text(current)
    if operator == "in":
        options = {
            part.strip() for part in str(compare or "").split(",") if part.strip()
        }
        if isinstance(current, (list, tuple)):
            return any(str(item) in options for item in current)
        return _as_text(current) in options
    left_number = _as_decimal(current)
    right_number = _as_decimal(compare)
    if (
        left_number is not None
        and right_number is not None
        and operator
        in {
            "gt",
            "gte",
            "lt",
            "lte",
            "equals",
            "not_equals",
        }
    ):
        if operator == "gt":
            return left_number > right_number
        if operator == "gte":
            return left_number >= right_number
        if operator == "lt":
            return left_number < right_number
        if operator == "lte":
            return left_number <= right_number
        if operator == "equals":
            return left_number == right_number
        return left_number != right_number
    left = _as_text(current)
    right = str(compare or "").strip()
    if operator == "equals":
        return left == right
    if operator == "not_equals":
        return left != right
    if operator == "gt":
        return left > right
    if operator == "gte":
        return left >= right
    if operator == "lt":
        return left < right
    if operator == "lte":
        return left <= right
    return False


def evaluate_rules(fields, rules, values):
    """Return ``(visible_by_key, required_by_key)`` after rules run in order."""
    visible = {}
    required = {}
    by_key = {}
    for field in fields:
        by_key[field.key] = field
        if field.field_type == FieldType.INSTRUCTION:
            visible[field.key] = True
            required[field.key] = False
            continue
        visible[field.key] = not field.is_hidden_by_default
        required[field.key] = field.required
    ordered = sorted(rules, key=lambda rule: (rule.order, rule.pk or 0))
    for rule in ordered:
        if not rule.is_active or rule.target_field_key not in visible:
            continue
        if not condition_matches(
            rule.operator,
            values.get(rule.source_field_key),
            rule.compare_value,
        ):
            continue
        if rule.action == "show":
            visible[rule.target_field_key] = True
        elif rule.action == "hide":
            visible[rule.target_field_key] = False
        elif rule.action == "require":
            required[rule.target_field_key] = True
        elif rule.action == "optional":
            required[rule.target_field_key] = False
    for field in fields:
        if field.source != "core":
            continue
        definition = get_core_field(
            field.version.template.function_type, field.core_key
        )
        if definition is not None and definition.required:
            visible[field.key] = True
            required[field.key] = True
    for key, shown in visible.items():
        if not shown:
            required[key] = False
    return visible, required


def _bounds(field):
    minimum = field.min_value
    maximum = field.max_value
    if field.field_type == FieldType.PERCENT:
        if minimum is None:
            minimum = Decimal("0")
        if maximum is None:
            maximum = Decimal("100")
    return minimum, maximum


def parse_posted(field, raw, upload=None, *, phong_id=None):
    """Convert one posted value. Empty input returns None."""
    label = field.label
    if field.field_type in FILE_TYPES:
        if upload in (None, False):
            return None
        try:
            validate_upload(upload, field)
        except ValidationError as exc:
            raise ValidationError(f"{label}: {exc.messages[0]}") from exc
        return upload
    if field.field_type == FieldType.MULTI_SELECT:
        if isinstance(raw, str):
            items = [raw] if raw else []
        else:
            items = [str(item) for item in (raw or []) if str(item).strip()]
        if not items:
            return []
        allowed = {option.value for option in field.options.all() if option.is_active}
        if any(item not in allowed for item in items):
            raise ValidationError(f"{label} có lựa chọn không hợp lệ.")
        return items
    if field.field_type in BOOL_TYPES:
        if raw in (True, "true", "on", "1", "True"):
            return True
        return False
    text = "" if raw is None else str(raw).strip()
    if text == "":
        return None
    if field.field_type in {"text", "textarea", "select", "radio"}:
        if field.field_type in {"select", "radio"}:
            allowed = {
                option.value for option in field.options.all() if option.is_active
            }
            if text not in allowed:
                raise ValidationError(f"{label} có lựa chọn không hợp lệ.")
        if field.min_length is not None and len(text) < field.min_length:
            raise ValidationError(f"{label} phải có ít nhất {field.min_length} ký tự.")
        if field.max_length is not None and len(text) > field.max_length:
            raise ValidationError(
                f"{label} không được dài quá {field.max_length} ký tự."
            )
        if field.regex:
            if compile_regex(field.regex).search(text) is None:
                raise ValidationError(f"{label} chưa đúng định dạng yêu cầu.")
        return text
    if field.field_type == FieldType.EMAIL:
        try:
            validate_email_value(text)
        except ValidationError as exc:
            raise ValidationError(f"Vui lòng nhập email hợp lệ cho {label}.") from exc
        return text
    if field.field_type == FieldType.PHONE:
        try:
            return normalize_phone(text)
        except ValidationError as exc:
            raise ValidationError(f"{label}: {exc.messages[0]}") from exc
    if field.field_type == FieldType.URL:
        try:
            validate_url_value(text)
        except ValidationError as exc:
            raise ValidationError(
                f"Vui lòng nhập đường dẫn hợp lệ cho {label}."
            ) from exc
        return text
    if field.field_type == FieldType.LOOKUP:
        try:
            obj = resolve_lookup(field.catalog_source, text, phong_id)
        except ValidationError as exc:
            message = exc.messages[0] if getattr(exc, "messages", None) else str(exc)
            raise ValidationError(f"{label}: {message}") from exc
        return None if obj is None else str(obj.pk)
    if field.field_type in NUMBER_TYPES:
        try:
            number = Decimal(text.replace(",", "."))
        except InvalidOperation as exc:
            raise ValidationError(f"Vui lòng nhập số hợp lệ cho {label}.") from exc
        if (
            field.field_type == FieldType.INTEGER
            and number != number.to_integral_value()
        ):
            raise ValidationError(f"{label} phải là số nguyên.")
        minimum, maximum = _bounds(field)
        if minimum is not None and number < minimum:
            raise ValidationError(f"{label} không được nhỏ hơn {minimum}.")
        if maximum is not None and number > maximum:
            raise ValidationError(f"{label} không được lớn hơn {maximum}.")
        return number
    if field.field_type == FieldType.DATE:
        parsed = parse_date(text)
        if parsed is None:
            raise ValidationError(f"Vui lòng nhập ngày hợp lệ cho {label}.")
        return parsed
    if field.field_type == FieldType.TIME:
        parsed = parse_time(text)
        if parsed is None:
            raise ValidationError(f"Vui lòng nhập giờ hợp lệ cho {label}.")
        return parsed
    if field.field_type == FieldType.DATETIME:
        parsed = parse_datetime(text)
        if parsed is None:
            raise ValidationError(f"Vui lòng nhập ngày giờ hợp lệ cho {label}.")
        if timezone.is_naive(parsed):
            parsed = timezone.make_aware(parsed, timezone.get_current_timezone())
        return parsed
    return text


def _columns(field_type, parsed):
    data = {
        "value_text": "",
        "value_number": None,
        "value_date": None,
        "value_time": None,
        "value_datetime": None,
        "value_bool": None,
        "value_json": None,
    }
    if parsed is None or parsed == []:
        return data
    if field_type in TEXT_TYPES or field_type in FILE_TYPES:
        data["value_text"] = (
            "" if parsed is None else str(getattr(parsed, "name", parsed))
        )
        if field_type in FILE_TYPES:
            data["value_text"] = sanitize_filename(getattr(parsed, "name", "") or "")
    elif field_type in NUMBER_TYPES:
        data["value_number"] = parsed
    elif field_type == FieldType.DATE:
        data["value_date"] = parsed
    elif field_type == FieldType.TIME:
        data["value_time"] = parsed
    elif field_type == FieldType.DATETIME:
        data["value_datetime"] = parsed
    elif field_type in BOOL_TYPES:
        data["value_bool"] = bool(parsed)
    elif field_type == FieldType.MULTI_SELECT:
        data["value_json"] = list(parsed)
    return data


def _stored_python(value):
    field_type = value.field.field_type
    if field_type in NUMBER_TYPES:
        return value.value_number
    if field_type == FieldType.DATE:
        return value.value_date
    if field_type == FieldType.TIME:
        return value.value_time
    if field_type == FieldType.DATETIME:
        return value.value_datetime
    if field_type in BOOL_TYPES:
        return value.value_bool
    if field_type == FieldType.MULTI_SELECT:
        return value.value_json or []
    if field_type in FILE_TYPES:
        return value.value_text or None
    return value.value_text or None


def stored_values(response):
    """Return ``{(field_key, so_lieu_id): python value}`` for one response."""
    rows = response.values.select_related("field").prefetch_related("attachments")
    return {(row.field_key, row.so_lieu_id): _stored_python(row) for row in rows}


def widget_value(field, parsed):
    """Return the text a bound widget should display."""
    if parsed is None or parsed == "":
        return ""
    if field.field_type == FieldType.MULTI_SELECT:
        return list(parsed or [])
    if field.field_type in BOOL_TYPES:
        return bool(parsed)
    if field.field_type == FieldType.DATE and hasattr(parsed, "isoformat"):
        return parsed.isoformat()
    if field.field_type == FieldType.TIME and hasattr(parsed, "strftime"):
        return parsed.strftime("%H:%M")
    if field.field_type == FieldType.DATETIME and hasattr(parsed, "strftime"):
        moment = parsed
        if timezone.is_aware(moment):
            moment = timezone.localtime(moment)
        return moment.strftime("%Y-%m-%dT%H:%M")
    if field.field_type in NUMBER_TYPES:
        text = format(parsed, "f")
        if "." in text:
            text = text.rstrip("0").rstrip(".")
        return text
    return str(parsed)


def _option_label(field, stored):
    options = {option.value: option.label for option in field.options.all()}
    return options.get(str(stored), str(stored))


def display_value(field, parsed, attachments=()):
    if field.field_type in FILE_TYPES:
        if not attachments:
            return "—"
        return attachments
    if is_empty(parsed) or parsed is False and field.field_type not in BOOL_TYPES:
        return "—"
    if field.field_type in BOOL_TYPES:
        return "Có" if parsed else "Không"
    if field.field_type in NUMBER_TYPES:
        text = format_vi_number(parsed)
        if field.field_type == FieldType.PERCENT and text != "—":
            return f"{text}%"
        return text
    if field.field_type == FieldType.DATE:
        return parsed.strftime("%d/%m/%Y")
    if field.field_type == FieldType.TIME:
        return parsed.strftime("%H:%M")
    if field.field_type == FieldType.DATETIME:
        moment = parsed
        if timezone.is_aware(moment):
            moment = timezone.localtime(moment)
        return moment.strftime("%d/%m/%Y %H:%M")
    if field.field_type == FieldType.MULTI_SELECT:
        return ", ".join(_option_label(field, item) for item in parsed) or "—"
    if field.field_type in {"select", "radio"}:
        return _option_label(field, parsed)
    if field.field_type == FieldType.LOOKUP:
        from apps.formbuilder.lookups import lookup_queryset

        queryset = lookup_queryset(
            field.catalog_source, field.version.template.phong_id
        )
        if queryset is None:
            return "—"
        obj = queryset.filter(pk=parsed).first()
        return str(obj) if obj is not None else "—"
    return str(parsed)


def echo_text(phieu, core_key):
    """Read-only text for a core field the existing screen already stores."""
    activity = phieu.hoat_dong if phieu.hoat_dong_id else None
    project = phieu.du_an if phieu.du_an_id else None
    if core_key == "ten" and activity:
        return activity.ten
    if core_key == "tu_ngay" and activity and activity.tu_ngay:
        return activity.tu_ngay.strftime("%d/%m/%Y")
    if core_key == "den_ngay" and activity and activity.den_ngay:
        return activity.den_ngay.strftime("%d/%m/%Y")
    if core_key == "dia_diem" and activity:
        return activity.dia_diem or "—"
    if core_key == "hinh_thuc" and activity:
        return activity.get_hinh_thuc_display()
    if core_key == "linh_vuc" and activity:
        return str(activity.linh_vuc) if activity.linh_vuc_id else "—"
    if core_key == "doi_tuong_huong_toi" and activity:
        names = list(
            activity.doi_tuong_huong_toi.order_by("ten_doi_tuong").values_list(
                "ten_doi_tuong",
                flat=True,
            )
        )
        return ", ".join(names) or "—"
    if core_key == "don_vi_phoi_hop" and activity:
        names = list(
            activity.don_vi_tham_gia.select_related("don_vi")
            .order_by("don_vi__ten_don_vi")
            .values_list("don_vi__ten_don_vi", flat=True)
        )
        return ", ".join(names) or "—"
    if core_key == "noi_dung" and activity:
        return activity.noi_dung or "—"
    if core_key == "ket_qua" and activity:
        return activity.ket_qua or "—"
    if core_key == "ten_du_an" and project:
        return project.ten_du_an
    if core_key == "chuong_trinh" and project:
        return project.get_chuong_trinh_display()
    if core_key == "hinh_thuc" and project:
        return project.get_hinh_thuc_display()
    if core_key == "nam" and project:
        return str(project.nam)
    if core_key == "phong" and project:
        return str(project.phong)
    return "—"


def echo_raw(phieu, core_key):
    """Machine value used when a rule reads a core field."""
    activity = phieu.hoat_dong if getattr(phieu, "hoat_dong_id", None) else None
    project = phieu.du_an if getattr(phieu, "du_an_id", None) else None
    if activity is not None and hasattr(activity, core_key):
        value = getattr(activity, core_key)
        if core_key == "doi_tuong_huong_toi":
            return [str(item) for item in value.values_list("pk", flat=True)]
        if hasattr(value, "pk"):
            return str(value.pk)
        return value
    if project is not None and core_key in {
        "ten_du_an",
        "chuong_trinh",
        "hinh_thuc",
        "nam",
        "phong",
    }:
        if core_key == "phong":
            return str(project.phong_id)
        return getattr(project, core_key)
    return None


def _replace_file(value_row, upload, field):
    for old in list(value_row.attachments.all()):
        if old.file:
            old.file.delete(save=False)
        old.delete()
    FormAttachment.objects.create(
        value=value_row,
        file=upload,
        original_name=sanitize_filename(upload.name),
        content_type=(getattr(upload, "content_type", "") or "")[:100],
        size=upload.size or 0,
    )


def _upsert(response, field, parsed, so_lieu, upload):
    defaults = _columns(
        field.field_type, parsed if field.field_type not in FILE_TYPES else upload
    )
    defaults["field_key"] = field.key
    lookup = {"response": response, "field": field, "so_lieu": so_lieu}
    existing = FormValue.objects.filter(**lookup).first()
    if existing is None:
        existing = FormValue.objects.create(**lookup, **defaults)
    else:
        for name, value in defaults.items():
            setattr(existing, name, value)
        existing.save()
    if field.field_type in FILE_TYPES and upload not in (None, False):
        _replace_file(existing, upload, field)
    return existing


def _get_response(phieu, version, user):
    response = (
        FormResponse.objects.filter(phieu=phieu, template=version.template)
        .select_related("template_version")
        .first()
    )
    if response is not None:
        return response
    response = FormResponse(
        phieu=phieu,
        template=version.template,
        template_version=version,
        created_by=user,
        updated_by=user,
    )
    response.save()
    return response


@transaction.atomic
def save_entries(phieu, version, user, entries):
    """Upsert visible custom values.

    ``entries`` is a list of dicts: field, parsed, upload, so_lieu, keep_file.
    Hidden fields are simply omitted by the caller.
    """
    if (
        not entries
        and not FormResponse.objects.filter(
            phieu=phieu,
            template=version.template,
        ).exists()
    ):
        return None
    response = _get_response(phieu, version, user)
    if response.template_version_id != version.id:
        version = response.template_version
    response.updated_by = user
    response.save(update_fields=["updated_by", "updated_at"])
    allowed = {field.key: field for field in version.fields.filter(source="custom")}
    for entry in entries:
        field = allowed.get(entry["field"].key)
        if field is None or field.field_type == FieldType.INSTRUCTION:
            continue
        if field.version_id != version.id:
            continue
        _upsert(
            response,
            field,
            entry.get("parsed"),
            entry.get("so_lieu"),
            entry.get("upload"),
        )
    return response


def render_readonly(response):
    """Group visible custom values in section order for detail and print."""
    from apps.formbuilder.services import load_version

    version = load_version(response.template_version)
    rows = list(
        response.values.select_related("field", "so_lieu").prefetch_related(
            "attachments",
            "field__options",
        )
    )
    form_values = {}
    row_bucket = {}
    for row in rows:
        parsed = _stored_python(row)
        if row.so_lieu_id is None:
            form_values[row.field_key] = parsed
        else:
            row_bucket.setdefault(row.so_lieu_id, {})[row.field_key] = row
    fields = [
        field for section in version.sections.all() for field in section.fields.all()
    ]
    visible, _required = evaluate_rules(fields, list(version.rules.all()), form_values)
    sections = []
    for section in version.sections.all():
        items = []
        for field in section.fields.all():
            if field.is_per_row:
                continue
            if not visible.get(field.key, True):
                continue
            if field.field_type == FieldType.INSTRUCTION:
                items.append(
                    {
                        "kind": "instruction",
                        "label": field.label,
                        "help_text": field.help_text,
                    }
                )
                continue
            if field.source != "custom":
                continue
            stored = next(
                (
                    row
                    for row in rows
                    if row.field_id == field.id and row.so_lieu_id is None
                ),
                None,
            )
            parsed = _stored_python(stored) if stored is not None else None
            attachments = list(stored.attachments.all()) if stored is not None else []
            items.append(
                {
                    "kind": "value",
                    "label": field.label,
                    "display": display_value(field, parsed, attachments),
                    "attachments": attachments,
                    "span_class": f"form-span-{field.col_span}",
                }
            )
        if items:
            sections.append(
                {
                    "title": section.title,
                    "description": section.description,
                    "items": items,
                }
            )
    per_row = {}
    for so_lieu_id, bucket in row_bucket.items():
        per_row[so_lieu_id] = []
        for field_key, row in bucket.items():
            field = row.field
            if not visible.get(field.key, True):
                continue
            per_row[so_lieu_id].append(
                {
                    "label": field.label,
                    "display": display_value(
                        field,
                        _stored_python(row),
                        list(row.attachments.all()),
                    ),
                    "attachments": list(row.attachments.all()),
                }
            )
    return {"sections": sections, "rows": per_row}
