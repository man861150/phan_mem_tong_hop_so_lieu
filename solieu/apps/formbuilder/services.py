"""Create, publish, and resolve form templates.

Entry screens call this module. They never trust a template id from the
request. Resolution is specific target, then the department generic template,
then no template.
"""

import re
from datetime import datetime

from django.core.exceptions import ValidationError
from django.db import IntegrityError, transaction
from django.db.models import Max, Prefetch
from django.utils import timezone

from apps.formbuilder.core import core_fields_for, get_core_field
from apps.formbuilder.models import (
    FormField,
    FormFieldOption,
    FormRule,
    FormSection,
    FormTemplate,
    FormTemplateVersion,
    FunctionType,
    VersionStatus,
    build_scope_key,
)
from apps.formbuilder.validators import has_cycle, parse_extensions

_FOLD = str.maketrans(
    {
        "à": "a",
        "á": "a",
        "ạ": "a",
        "ả": "a",
        "ã": "a",
        "â": "a",
        "ầ": "a",
        "ấ": "a",
        "ậ": "a",
        "ẩ": "a",
        "ẫ": "a",
        "ă": "a",
        "ằ": "a",
        "ắ": "a",
        "ặ": "a",
        "ẳ": "a",
        "ẵ": "a",
        "è": "e",
        "é": "e",
        "ẹ": "e",
        "ẻ": "e",
        "ẽ": "e",
        "ê": "e",
        "ề": "e",
        "ế": "e",
        "ệ": "e",
        "ể": "e",
        "ễ": "e",
        "ì": "i",
        "í": "i",
        "ị": "i",
        "ỉ": "i",
        "ĩ": "i",
        "ò": "o",
        "ó": "o",
        "ọ": "o",
        "ỏ": "o",
        "õ": "o",
        "ô": "o",
        "ồ": "o",
        "ố": "o",
        "ộ": "o",
        "ổ": "o",
        "ỗ": "o",
        "ơ": "o",
        "ờ": "o",
        "ớ": "o",
        "ợ": "o",
        "ở": "o",
        "ỡ": "o",
        "ù": "u",
        "ú": "u",
        "ụ": "u",
        "ủ": "u",
        "ũ": "u",
        "ư": "u",
        "ừ": "u",
        "ứ": "u",
        "ự": "u",
        "ử": "u",
        "ữ": "u",
        "ỳ": "y",
        "ý": "y",
        "ỵ": "y",
        "ỷ": "y",
        "ỹ": "y",
        "đ": "d",
    }
)

DEFAULT_LABELS = {
    "text": "Văn bản",
    "textarea": "Đoạn văn",
    "integer": "Số nguyên",
    "decimal": "Số thập phân",
    "percent": "Phần trăm",
    "date": "Ngày",
    "time": "Giờ",
    "datetime": "Ngày giờ",
    "select": "Lựa chọn",
    "multi_select": "Chọn nhiều",
    "radio": "Chọn một",
    "checkbox": "Hộp kiểm",
    "switch": "Công tắc",
    "email": "Email",
    "phone": "Số điện thoại",
    "url": "Đường dẫn",
    "file": "Tệp đính kèm",
    "image": "Hình ảnh",
    "lookup": "Danh mục",
    "instruction": "Hướng dẫn",
}

PALETTE = (
    ("Cơ bản", ("text", "textarea", "instruction")),
    ("Lựa chọn", ("select", "multi_select", "radio", "checkbox", "switch")),
    ("Ngày giờ", ("date", "time", "datetime")),
    ("Số", ("integer", "decimal", "percent")),
    ("Nâng cao", ("email", "phone", "url", "file", "image", "lookup")),
)

DUPLICATE_SCOPE_MESSAGE = "Đã có biểu mẫu đang hoạt động cho phạm vi này."


class PublishError(Exception):
    """Publish checklist failed. ``errors`` are Vietnamese sentences."""

    def __init__(self, errors):
        self.errors = list(errors)
        super().__init__("; ".join(self.errors))


def load_version(version):
    pk = version.pk if hasattr(version, "pk") else version
    sections = FormSection.objects.order_by("order", "id").prefetch_related(
        Prefetch(
            "fields",
            queryset=FormField.objects.order_by("order", "id").prefetch_related(
                "options"
            ),
        )
    )
    return (
        FormTemplateVersion.objects.select_related(
            "template",
            "template__phong",
            "template__target_activity_type",
            "template__target_indicator_group",
            "published_by",
        )
        .prefetch_related(Prefetch("sections", queryset=sections), "rules")
        .get(pk=pk)
    )


def touch(version):
    now = timezone.now()
    FormTemplateVersion.objects.filter(pk=version.pk).update(updated_at=now)
    FormTemplate.objects.filter(pk=version.template_id).update(updated_at=now)
    version.updated_at = now


def _next_version_number(template):
    current = template.versions.aggregate(max_version=Max("version"))["max_version"]
    return (current or 0) + 1


def _copy_field(field, version, section, *, key=None):
    clone = FormField(
        version=version,
        section=section,
        key=key or field.key,
        label=field.label,
        field_type=field.field_type,
        source=field.source,
        core_key=field.core_key,
        required=field.required,
        read_only=field.read_only,
        default_value=field.default_value,
        placeholder=field.placeholder,
        help_text=field.help_text,
        order=field.order,
        col_span=field.col_span,
        is_hidden_by_default=field.is_hidden_by_default,
        is_per_row=field.is_per_row,
        min_value=field.min_value,
        max_value=field.max_value,
        min_length=field.min_length,
        max_length=field.max_length,
        regex=field.regex,
        max_file_size_mb=field.max_file_size_mb,
        allowed_extensions=field.allowed_extensions,
        unique_within_form=field.unique_within_form,
        catalog_source=field.catalog_source,
    )
    clone.save()
    for option in field.options.all().order_by("order", "id"):
        FormFieldOption.objects.create(
            field=clone,
            label=option.label,
            value=option.value,
            order=option.order,
            is_active=option.is_active,
        )
    return clone


def clone_version(source, *, template=None, status=None, version_number=None):
    """Copy sections, fields, options, and rules onto a new draft version."""
    template = template or source.template
    clone = FormTemplateVersion(
        template=template,
        version=version_number or _next_version_number(template),
        status=status or VersionStatus.DRAFT,
        layout_notes=source.layout_notes,
    )
    clone.save()
    section_map = {}
    for section in source.sections.all().order_by("order", "id"):
        copied = FormSection.objects.create(
            version=clone,
            title=section.title,
            description=section.description,
            order=section.order,
            columns=section.columns,
            is_collapsible=section.is_collapsible,
            is_collapsed=section.is_collapsed,
        )
        section_map[section.pk] = copied
    for field in source.fields.select_related("section").order_by("order", "id"):
        _copy_field(field, clone, section_map[field.section_id])
    for rule in source.rules.all().order_by("order", "id"):
        FormRule.objects.create(
            version=clone,
            source_field_key=rule.source_field_key,
            operator=rule.operator,
            compare_value=rule.compare_value,
            action=rule.action,
            target_field_key=rule.target_field_key,
            order=rule.order,
            is_active=rule.is_active,
        )
    return clone


def _seed_core(version, section, function_type):
    for index, definition in enumerate(core_fields_for(function_type), start=1):
        FormField.objects.create(
            version=version,
            section=section,
            key=definition.key,
            label=definition.label,
            field_type=definition.field_type,
            source="core",
            core_key=definition.core_key,
            required=definition.required,
            read_only=True,
            order=index,
            col_span=12,
        )


@transaction.atomic
def create_template(
    *,
    phong,
    name,
    function_type,
    user,
    description="",
    activity_type=None,
    group=None,
):
    template = FormTemplate(
        phong=phong,
        name=name,
        description=description or "",
        function_type=function_type,
        target_activity_type=activity_type,
        target_indicator_group=group,
        created_by=user,
        scope_key=build_scope_key(
            function_type,
            getattr(activity_type, "pk", None),
            getattr(group, "pk", None),
        ),
    )
    template.save()
    version = FormTemplateVersion.objects.create(
        template=template,
        version=1,
        status=VersionStatus.DRAFT,
    )
    section = FormSection.objects.create(
        version=version,
        title="Thông tin chung",
        order=1,
        columns=1,
    )
    _seed_core(version, section, function_type)
    template.current_draft = version
    template.save(update_fields=["current_draft", "updated_at"])
    return template


def ensure_draft(template):
    draft = template.current_draft
    if draft is not None and draft.status == VersionStatus.DRAFT:
        return draft
    published = template.current_published
    if published is None:
        raise ValidationError("Biểu mẫu chưa có bản nháp.")
    clone = clone_version(published)
    template.current_draft = clone
    template.save(update_fields=["current_draft", "updated_at"])
    return clone


def validate_for_publish(version):
    """Return Vietnamese checklist errors. An empty list means the draft can publish."""
    version = load_version(version)
    errors = []
    template = version.template
    if not (template.name or "").strip():
        errors.append("Biểu mẫu chưa có tên.")
    sections = list(version.sections.all())
    if not sections:
        errors.append("Biểu mẫu cần ít nhất một phần.")
    fields = [field for section in sections for field in section.fields.all()]
    if not any(field.field_type != "instruction" for field in fields):
        errors.append("Biểu mẫu cần ít nhất một trường nhập liệu.")
    seen_keys = set()
    for field in fields:
        if not (field.label or "").strip():
            errors.append("Có trường chưa có nhãn.")
        if field.key in seen_keys:
            errors.append(f"Mã trường “{field.key}” bị trùng.")
        seen_keys.add(field.key)
        if field.regex:
            try:
                re.compile(field.regex)
            except re.error:
                errors.append(f"Biểu thức của “{field.label}” không hợp lệ.")
        if field.field_type in {"file", "image"}:
            extensions = parse_extensions(field.allowed_extensions)
            if not extensions:
                errors.append(f"“{field.label}” chưa có phần mở rộng được phép.")
            if field.field_type == "image" and any(
                ext not in {"jpg", "jpeg", "png", "gif", "webp"} for ext in extensions
            ):
                errors.append(f"“{field.label}” chỉ nhận tệp hình ảnh.")
            if field.max_file_size_mb is not None and (
                field.max_file_size_mb < 1 or field.max_file_size_mb > 25
            ):
                errors.append(f"Dung lượng của “{field.label}” phải từ 1 đến 25 MB.")
        if field.is_choice and field.source == "custom":
            if not any(option.is_active for option in field.options.all()):
                errors.append(f"“{field.label}” cần ít nhất một lựa chọn.")
    present = {field.core_key for field in fields if field.source == "core"}
    for definition in core_fields_for(template.function_type):
        if definition.required and definition.core_key not in present:
            errors.append(f"Thiếu trường hệ thống “{definition.label}”.")
    rules = list(version.rules.all())
    keys = {field.key for field in fields}
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.source_field_key not in keys or rule.target_field_key not in keys:
            errors.append("Có điều kiện trỏ tới trường không tồn tại.")
        if rule.source_field_key == rule.target_field_key:
            errors.append("Có điều kiện trỏ vào chính trường nguồn.")
    if has_cycle(rules):
        errors.append("Các điều kiện đang tạo vòng lặp.")
    return errors


@transaction.atomic
def publish_template(template, user):
    template = FormTemplate.objects.select_for_update().get(pk=template.pk)
    draft = template.current_draft
    if draft is None or draft.status != VersionStatus.DRAFT:
        raise PublishError(["Không có bản nháp để xuất bản."])
    errors = validate_for_publish(draft)
    if errors:
        raise PublishError(errors)
    now = timezone.now()
    for old in FormTemplateVersion.objects.filter(
        template=template,
        status=VersionStatus.PUBLISHED,
    ):
        old.status = VersionStatus.ARCHIVED
        old.save(update_fields=["status", "updated_at"])
    draft.status = VersionStatus.PUBLISHED
    draft.published_at = now
    draft.published_by = user
    draft.save()
    clone = clone_version(draft)
    template.current_published = draft
    template.current_draft = clone
    template.save(update_fields=["current_published", "current_draft", "updated_at"])
    return draft


@transaction.atomic
def duplicate_template(template, user):
    source = template.current_draft or template.current_published
    if source is None:
        raise ValidationError("Biểu mẫu chưa có nội dung để nhân bản.")
    copy = FormTemplate(
        phong=template.phong,
        name=f"{template.name} (bản sao)"[:255],
        description=template.description,
        function_type=template.function_type,
        target_activity_type=template.target_activity_type,
        target_indicator_group=template.target_indicator_group,
        created_by=user,
        is_active=False,
        scope_key=template.scope_key,
    )
    copy.save()
    draft = clone_version(source, template=copy, version_number=1)
    copy.current_draft = draft
    copy.save(update_fields=["current_draft", "updated_at"])
    return copy


def archive_template(template):
    template.is_active = False
    template.save(update_fields=["is_active", "updated_at"])
    return template


def restore_template(template):
    template.is_active = True
    try:
        template.save()
    except (ValidationError, IntegrityError) as exc:
        raise ValidationError(DUPLICATE_SCOPE_MESSAGE) from exc
    return template


@transaction.atomic
def replace_draft_from(template, version):
    template = FormTemplate.objects.select_for_update().get(pk=template.pk)
    if version.template_id != template.pk:
        raise ValidationError("Phiên bản không thuộc biểu mẫu này.")
    current = template.current_draft
    if current is not None and current.pk == version.pk:
        raise ValidationError("Phiên bản này đang là bản nháp.")
    if current is not None and current.responses.exists():
        raise ValidationError("Không thể thay bản nháp đã có phiếu.")
    clone = clone_version(version, version_number=_next_version_number(template))
    template.current_draft = clone
    template.save(update_fields=["current_draft", "updated_at"])
    if current is not None and current.status == VersionStatus.DRAFT:
        # Field.section is PROTECT, so fields go before the sections that
        # cascade from the version.
        current.fields.all().delete()
        current.rules.all().delete()
        current.sections.all().delete()
        current.delete()
    return clone


def ascii_token(label):
    text = (label or "").lower().translate(_FOLD)
    text = re.sub(r"[^a-z0-9]+", "_", text).strip("_")
    return text[:40]


def next_custom_key(version, label):
    token = ascii_token(label) or "truong"
    base = f"cf_{token}"
    existing = set(version.fields.values_list("key", flat=True))
    if base not in existing and re.match(r"^cf_[a-z][a-z0-9_]*$", base):
        return base
    if not re.match(r"^cf_[a-z][a-z0-9_]*$", base):
        base = "cf_truong"
    number = 2
    candidate = base
    while candidate in existing:
        candidate = f"{base}_{number}"
        number += 1
    return candidate


def add_section(version, title="Phần mới"):
    if version.status != VersionStatus.DRAFT:
        raise ValidationError("Phiên bản đã xuất bản không thể sửa.")
    order = (version.sections.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
    section = FormSection.objects.create(
        version=version,
        title=title,
        order=order,
        columns=1,
    )
    touch(version)
    return section


def delete_section(section):
    version = section.version
    if version.sections.count() <= 1:
        raise ValidationError("Biểu mẫu phải còn ít nhất một phần.")
    for field in section.fields.all():
        definition = get_core_field(version.template.function_type, field.core_key)
        if field.source == "core" and definition is not None and definition.required:
            raise ValidationError(
                "Không thể xóa phần đang chứa trường hệ thống bắt buộc."
            )
    for field in list(section.fields.all()):
        field.delete()
    section.delete()
    touch(version)


def duplicate_section(section):
    version = section.version
    if version.status != VersionStatus.DRAFT:
        raise ValidationError("Phiên bản đã xuất bản không thể sửa.")
    order = (version.sections.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
    copy = FormSection.objects.create(
        version=version,
        title=f"{section.title} (bản sao)"[:255],
        description=section.description,
        order=order,
        columns=section.columns,
        is_collapsible=section.is_collapsible,
        is_collapsed=section.is_collapsed,
    )
    for field in section.fields.all().order_by("order", "id"):
        if field.source == "core":
            continue
        _copy_field(
            field,
            version,
            copy,
            key=next_custom_key(version, field.label),
        )
    touch(version)
    return copy


def add_field(version, field_type, section, *, label=None, key=None):
    if section.version_id != version.id:
        raise ValidationError("Phần không thuộc phiên bản này.")
    label = (label or DEFAULT_LABELS.get(field_type) or "Trường mới").strip()
    order = (section.fields.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
    per_row = version.template.function_type == FunctionType.CHI_TIEU
    field = FormField(
        version=version,
        section=section,
        key=key or next_custom_key(version, label),
        label=label,
        field_type=field_type,
        source="custom",
        order=order,
        col_span=12,
        is_per_row=per_row,
        catalog_source="doi_tuong" if field_type == "lookup" else "",
        help_text=label if field_type == "instruction" else "",
    )
    field.save()
    touch(version)
    return field


def add_core_field(version, section, core_key):
    definition = get_core_field(version.template.function_type, core_key)
    if definition is None:
        raise ValidationError("Trường hệ thống không thuộc chức năng này.")
    if version.fields.filter(key=definition.key).exists():
        raise ValidationError("Trường hệ thống đã có trên biểu mẫu.")
    order = (section.fields.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
    field = FormField(
        version=version,
        section=section,
        key=definition.key,
        label=definition.label,
        field_type=definition.field_type,
        source="core",
        core_key=definition.core_key,
        required=definition.required,
        read_only=True,
        order=order,
        col_span=12,
    )
    field.save()
    touch(version)
    return field


def option_value(field, label):
    token = ascii_token(label) or "lua_chon"
    token = token[:80]
    existing = set(field.options.values_list("value", flat=True))
    candidate = token
    number = 2
    while candidate in existing:
        candidate = f"{token}_{number}"[:100]
        number += 1
    return candidate


def add_option(field, label, value=""):
    label = (label or "").strip()
    value = (value or "").strip() or option_value(field, label)
    order = (field.options.aggregate(max_order=Max("order"))["max_order"] or 0) + 1
    option = FormFieldOption(field=field, label=label, value=value, order=order)
    option.save()
    touch(field.version)
    return option


@transaction.atomic
def reorder(version, section_ids, field_specs):
    """Persist an exact permutation of this draft's sections and fields."""
    if version.status != VersionStatus.DRAFT:
        raise ValidationError("Phiên bản đã xuất bản không thể sửa.")
    sections = list(version.sections.all())
    fields = list(version.fields.all())
    if len(section_ids) != len(set(section_ids)) or set(section_ids) != {
        section.pk for section in sections
    }:
        raise ValidationError("Danh sách phần không khớp biểu mẫu.")
    field_ids = [spec["id"] for spec in field_specs]
    if len(field_ids) != len(set(field_ids)) or set(field_ids) != {
        field.pk for field in fields
    }:
        raise ValidationError("Danh sách trường không khớp biểu mẫu.")
    allowed_sections = set(section_ids)
    by_section = {section.pk: section for section in sections}
    by_field = {field.pk: field for field in fields}
    for index, section_id in enumerate(section_ids, start=1):
        section = by_section[section_id]
        section.order = index
        section.save(update_fields=["order"])
    for spec in field_specs:
        if spec["section_id"] not in allowed_sections:
            raise ValidationError("Trường được chuyển tới phần không thuộc biểu mẫu.")
        field = by_field[spec["id"]]
        field.section = by_section[spec["section_id"]]
        field.order = spec["order"]
        field.save(update_fields=["section", "order"])
    touch(version)


def move_field(field, *, direction=None, section_id=None):
    """Move one field up, down, or into another section and renormalize order."""
    version = field.version
    sections = list(version.sections.order_by("order", "id"))
    section_ids = [section.pk for section in sections]
    specs = []
    grouped = {section.pk: [] for section in sections}
    for item in version.fields.order_by("order", "id"):
        grouped[item.section_id].append(item)
    if section_id is not None and section_id != field.section_id:
        grouped[field.section_id] = [
            item for item in grouped[field.section_id] if item.pk != field.pk
        ]
        grouped[section_id].append(field)
    elif direction in {"up", "down"}:
        bucket = grouped[field.section_id]
        index = next(i for i, item in enumerate(bucket) if item.pk == field.pk)
        swap = index - 1 if direction == "up" else index + 1
        if 0 <= swap < len(bucket):
            bucket[index], bucket[swap] = bucket[swap], bucket[index]
    for section_id_value, bucket in grouped.items():
        for index, item in enumerate(bucket, start=1):
            specs.append(
                {"id": item.pk, "section_id": section_id_value, "order": index}
            )
    reorder(version, section_ids, specs)


def move_section(section, direction):
    version = section.version
    sections = list(version.sections.order_by("order", "id"))
    index = next(i for i, item in enumerate(sections) if item.pk == section.pk)
    swap = index - 1 if direction == "up" else index + 1
    if swap < 0 or swap >= len(sections):
        return
    sections[index], sections[swap] = sections[swap], sections[index]
    specs = [
        {"id": field.pk, "section_id": field.section_id, "order": field.order}
        for field in version.fields.all()
    ]
    reorder(version, [item.pk for item in sections], specs)


def _active_templates(phong_id):
    return FormTemplate.objects.filter(
        phong_id=phong_id,
        is_active=True,
        current_published__isnull=False,
    ).select_related("current_published")


def _published_for_scope(phong_id, specific_key, generic_key):
    queryset = _active_templates(phong_id)
    if specific_key:
        match = queryset.filter(scope_key=specific_key).first()
        if match is not None:
            return match
    return queryset.filter(scope_key=generic_key).first()


def _pinned_version(phieu, function_type, *, group_id=None):
    """Keep the version already stored on this phiếu, including after archive."""
    from apps.formbuilder.models import FormResponse

    responses = FormResponse.objects.filter(
        phieu=phieu,
        template__function_type=function_type,
    ).select_related("template", "template_version")
    specific = None
    generic = None
    for response in responses:
        target = response.template.target_indicator_group_id
        if function_type == FunctionType.CHI_TIEU and group_id and target == group_id:
            specific = response.template_version
        elif function_type == FunctionType.CHI_TIEU and target is None:
            generic = response.template_version
        elif function_type != FunctionType.CHI_TIEU:
            return response.template_version
    return specific or generic


def resolve_form_template(phieu):
    """Return the pinned or current published version for this phiếu, or None.

    A saved response wins, so a later publish or archive does not change the
    phiếu. New phiếu use the specific target, then the department generic
    template. The request never supplies a template id.
    """
    from apps.entry.models import LoaiPhieu

    if phieu.loai_phieu == LoaiPhieu.HOAT_DONG and phieu.hoat_dong_id:
        function_type = FunctionType.HOAT_DONG
        loai_id = phieu.hoat_dong.loai_hoat_dong_id
        specific, generic = f"hoat_dong:loai:{loai_id}", "hoat_dong:*"
    elif phieu.loai_phieu == LoaiPhieu.THANG:
        function_type = FunctionType.THANG
        specific, generic = None, "thang:*"
    elif phieu.loai_phieu == LoaiPhieu.DU_AN:
        function_type = FunctionType.DU_AN
        specific, generic = None, "du_an:*"
    else:
        return None
    pinned = _pinned_version(phieu, function_type)
    if pinned is not None:
        return pinned
    template = _published_for_scope(phieu.phong_id, specific, generic)
    if template is None:
        return None
    return template.current_published


def resolve_row_template(phieu, group_id):
    pinned = _pinned_version(phieu, FunctionType.CHI_TIEU, group_id=group_id)
    if pinned is not None:
        return pinned
    template = _published_for_scope(
        phieu.phong_id,
        f"chi_tieu:nhom:{group_id}" if group_id else None,
        "chi_tieu:*",
    )
    if template is None:
        return None
    return template.current_published


def saved_at_label(version):
    moment = timezone.localtime(version.updated_at)
    if timezone.localdate(version.updated_at) == timezone.localdate():
        return moment.strftime("%H:%M")
    return moment.strftime("%d/%m/%Y %H:%M")


def parse_datetime(value):
    if isinstance(value, datetime):
        return value
    text = (value or "").strip()
    if not text:
        return None
    return datetime.fromisoformat(text)
