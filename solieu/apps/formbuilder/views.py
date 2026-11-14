"""Form template list, designer, and version history."""

import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied, ValidationError
from django.db import IntegrityError
from django.http import FileResponse, HttpResponseBadRequest
from django.shortcuts import get_object_or_404, redirect, render
from django.views.decorators.http import require_GET, require_http_methods, require_POST

from apps.accounts.permissions import can
from apps.accounts.roles import SCOPED_ROLES
from apps.accounts.scoping import scoped
from apps.catalog.models import LoaiHoatDong, NhomChiTieu, PhongBan
from apps.entry.models import PhieuNhapLieu
from apps.formbuilder.core import core_fields_for
from apps.formbuilder.forms import (
    DynamicEntryForm,
    FieldUpdateForm,
    OptionForm,
    RuleForm,
    SectionForm,
    TemplateCreateForm,
    TemplateMetaForm,
)
from apps.formbuilder.lookups import CATALOG_LABELS
from apps.formbuilder.models import (
    FormAttachment,
    FormField,
    FormFieldOption,
    FormRule,
    FormSection,
    FormTemplate,
    FormTemplateVersion,
    FunctionType,
)
from apps.formbuilder.services import (
    PALETTE,
    PublishError,
    add_core_field,
    add_field,
    add_option,
    add_section,
    archive_template,
    create_template,
    delete_section,
    duplicate_section,
    duplicate_template,
    ensure_draft,
    load_version,
    move_field,
    move_section,
    publish_template,
    reorder,
    replace_draft_from,
    restore_template,
    saved_at_label,
)
from apps.formbuilder.values import evaluate_rules


def _error_text(exc):
    if hasattr(exc, "message_dict"):
        parts = []
        for errors in exc.message_dict.values():
            parts.extend(str(item) for item in errors)
        if parts:
            return " ".join(parts)
    if hasattr(exc, "messages"):
        return " ".join(str(item) for item in exc.messages)
    return str(exc)


def _templates_for(user):
    return scoped(
        user,
        FormTemplate.objects.select_related(
            "phong",
            "target_activity_type",
            "target_indicator_group",
            "current_draft",
            "current_published",
        ),
        "phong_id",
    )


def _require_action(user, action):
    if not can(user, action):
        raise PermissionDenied


def _template_for(user, pk, action):
    _require_action(user, action)
    template = get_object_or_404(_templates_for(user), pk=pk)
    if not can(user, action, template.phong_id):
        raise PermissionDenied
    return template


def _owner_template(obj):
    if isinstance(obj, FormSection):
        return obj.version.template
    if isinstance(obj, FormField):
        return obj.version.template
    if isinstance(obj, FormFieldOption):
        return obj.field.version.template
    if isinstance(obj, FormRule):
        return obj.version.template
    return obj


def _in_scope(user, template):
    return _templates_for(user).filter(pk=template.pk).exists()


def _load_child(user, model, pk, action):
    _require_action(user, action)
    obj = get_object_or_404(model.objects.select_related(), pk=pk)
    template = _owner_template(obj)
    if not _in_scope(user, template):
        from django.http import Http404

        raise Http404("Không tìm thấy biểu mẫu.")
    if not can(user, action, template.phong_id):
        raise PermissionDenied
    return obj


def _builder_context(request, form_template, draft, selected_id=None):
    draft = load_version(draft)
    fields = [
        field for section in draft.sections.all() for field in section.fields.all()
    ]
    present = {field.core_key for field in fields if field.source == "core"}
    unused = [
        definition
        for definition in core_fields_for(form_template.function_type)
        if definition.core_key not in present
    ]
    selected = None
    if selected_id:
        selected = next(
            (field for field in fields if field.pk == int(selected_id)), None
        )
    if selected is None and fields:
        selected = fields[0]
    inspector = None
    rule_form = None
    option_form = None
    if selected is not None:
        inspector = _inspector_form(selected)
        rule_form = _rule_form(draft)
        option_form = OptionForm()
    sections = list(draft.sections.all())
    return {
        "form_template": form_template,
        "draft": draft,
        "published": form_template.current_published,
        "default_section_id": (
            selected.section_id
            if selected is not None
            else (sections[0].pk if sections else "")
        ),
        "palette": [
            (label, [(code, dict(PALETTE_LABELS).get(code, code)) for code in codes])
            for label, codes in PALETTE
        ],
        "unused_core": unused,
        "selected_field": selected,
        "inspector_form": inspector,
        "rule_form": rule_form,
        "option_form": option_form,
        "field_rules": _rules_for(draft, selected),
        "can_edit": can(request.user, "design_form_template", form_template.phong_id),
        "can_publish": can(
            request.user,
            "publish_form_template",
            form_template.phong_id,
        ),
        "can_archive": can(
            request.user,
            "archive_form_template",
            form_template.phong_id,
        ),
        "save_label": saved_at_label(draft),
        "read_only": not can(
            request.user,
            "design_form_template",
            form_template.phong_id,
        ),
    }


PALETTE_LABELS = {
    "text": "Văn bản",
    "textarea": "Đoạn văn",
    "instruction": "Hướng dẫn",
    "select": "Danh sách",
    "multi_select": "Chọn nhiều",
    "radio": "Chọn một",
    "checkbox": "Hộp kiểm",
    "switch": "Công tắc",
    "date": "Ngày",
    "time": "Giờ",
    "datetime": "Ngày giờ",
    "integer": "Số nguyên",
    "decimal": "Số thập phân",
    "percent": "Phần trăm",
    "email": "Email",
    "phone": "Điện thoại",
    "url": "Đường dẫn",
    "file": "Tệp",
    "image": "Hình ảnh",
    "lookup": "Danh mục",
}


def _inspector_form(field, data=None):
    sections = field.version.sections.all()
    initial = (
        None
        if data is not None
        else {
            "label": field.label,
            "required": field.required,
            "read_only": field.read_only,
            "placeholder": field.placeholder,
            "help_text": field.help_text,
            "default_value": field.default_value,
            "col_span": field.col_span,
            "is_hidden_by_default": field.is_hidden_by_default,
            "is_per_row": field.is_per_row,
            "min_value": field.min_value,
            "max_value": field.max_value,
            "min_length": field.min_length,
            "max_length": field.max_length,
            "regex": field.regex,
            "max_file_size_mb": field.max_file_size_mb,
            "allowed_extensions": field.allowed_extensions,
            "unique_within_form": field.unique_within_form,
            "catalog_source": field.catalog_source,
            "section": field.section_id,
        }
    )
    return FieldUpdateForm(
        data,
        initial=initial,
        sections=sections,
        catalog_choices=list(CATALOG_LABELS.items()),
    )


def _rule_form(draft, data=None):
    choices = [
        (field.key, field.label)
        for section in draft.sections.all()
        for field in section.fields.all()
    ]
    return RuleForm(data, field_choices=choices)


def _rules_for(draft, field):
    if field is None:
        return []
    return [
        rule
        for rule in draft.rules.all()
        if rule.source_field_key == field.key or rule.target_field_key == field.key
    ]


def _render_builder(request, form_template, selected_id=None, status=200):
    draft = ensure_draft(form_template)
    context = _builder_context(request, form_template, draft, selected_id)
    if getattr(request, "htmx", False):
        return render(
            request,
            "formbuilder/partials/stage.html",
            context,
            status=status,
        )
    return render(request, "formbuilder/design.html", context, status=status)


@login_required
@require_GET
def template_list(request):
    _require_action(request.user, "view_form_templates")
    queryset = _templates_for(request.user)
    function_type = request.GET.get("chuc_nang", "")
    if function_type in FunctionType.values:
        queryset = queryset.filter(function_type=function_type)
    status = request.GET.get("trang_thai", "")
    if status == "nhap":
        queryset = queryset.filter(is_active=True, current_published__isnull=True)
    elif status == "xuat_ban":
        queryset = queryset.filter(is_active=True, current_published__isnull=False)
    elif status == "luu_tru":
        queryset = queryset.filter(is_active=False)
    query = (request.GET.get("q") or "").strip()
    if query:
        queryset = queryset.filter(name__icontains=query)
    phong_id = request.GET.get("phong") or ""
    if phong_id.isdigit() and request.user.role not in SCOPED_ROLES:
        queryset = queryset.filter(phong_id=int(phong_id))
    departments = []
    if request.user.role not in SCOPED_ROLES:
        departments = PhongBan.objects.filter(dang_su_dung=True).order_by("ma_phong")
    return render(
        request,
        "formbuilder/list.html",
        {
            "templates": queryset.order_by("phong__ma_phong", "name"),
            "function_type": function_type,
            "status": status,
            "query": query,
            "phong_id": phong_id,
            "departments": departments,
            "function_choices": FunctionType.choices,
            "can_create": can(request.user, "design_form_template"),
        },
    )


def _target_choices(phong):
    choices = [
        (f"loai:{row.pk}", f"Hoạt động — {row.ten_loai}")
        for row in LoaiHoatDong.objects.filter(phong=phong).order_by("ten_loai")
    ]
    choices.extend(
        (f"nhom:{row.pk}", f"Chỉ tiêu — {row.ten_mang}")
        for row in NhomChiTieu.objects.filter(phong=phong).order_by("ten_mang")
    )
    return choices


@login_required
@require_http_methods(["GET", "POST"])
def template_create(request):
    _require_action(request.user, "design_form_template")
    if request.user.role in SCOPED_ROLES:
        phong = request.user.phong
    else:
        phong_id = request.POST.get("phong") or request.GET.get("phong")
        phong = get_object_or_404(PhongBan, pk=phong_id) if phong_id else None
    form = TemplateCreateForm(
        request.POST or None,
        targets=_target_choices(phong) if phong else [],
    )
    if request.method == "POST" and phong is None:
        form.add_error(None, "Chọn phòng ban trước khi tạo biểu mẫu.")
    elif request.method == "POST" and form.is_valid():
        if not can(request.user, "design_form_template", phong.pk):
            raise PermissionDenied
        activity = None
        group = None
        target = form.cleaned_data["target"]
        function_type = form.cleaned_data["function_type"]
        try:
            if target.startswith("loai:"):
                activity = LoaiHoatDong.objects.get(
                    pk=int(target.split(":", 1)[1]),
                    phong=phong,
                )
            elif target.startswith("nhom:"):
                group = NhomChiTieu.objects.get(
                    pk=int(target.split(":", 1)[1]),
                    phong=phong,
                )
        except LoaiHoatDong.DoesNotExist, NhomChiTieu.DoesNotExist, ValueError:
            form.add_error("target", "Phạm vi không thuộc phòng này.")
        else:
            if function_type == FunctionType.HOAT_DONG and group is not None:
                form.add_error(
                    "target", "Biểu mẫu hoạt động chỉ chọn loại hoạt động hoặc Tất cả."
                )
            elif function_type == FunctionType.CHI_TIEU and activity is not None:
                form.add_error(
                    "target", "Biểu mẫu chỉ tiêu chỉ chọn nhóm chỉ tiêu hoặc Tất cả."
                )
            elif function_type in {FunctionType.DU_AN, FunctionType.THANG} and target:
                form.add_error("target", "Chức năng này chỉ dùng phạm vi Tất cả.")
            else:
                try:
                    created = create_template(
                        phong=phong,
                        name=form.cleaned_data["name"],
                        function_type=function_type,
                        user=request.user,
                        description=form.cleaned_data["description"],
                        activity_type=activity,
                        group=group,
                    )
                except (ValidationError, IntegrityError) as exc:
                    form.add_error(
                        None,
                        _error_text(exc)
                        or "Đã có biểu mẫu đang hoạt động cho phạm vi này.",
                    )
                else:
                    return redirect("formbuilder:design", pk=created.pk)
    return render(
        request,
        "formbuilder/create.html",
        {
            "form": form,
            "phong": phong,
            "departments": PhongBan.objects.filter(dang_su_dung=True).order_by(
                "ma_phong"
            )
            if request.user.role not in SCOPED_ROLES
            else [],
        },
    )


@login_required
@require_GET
def template_design(request, pk):
    form_template = _template_for(request.user, pk, "view_form_templates")
    return _render_builder(request, form_template, request.GET.get("truong"))


@login_required
@require_POST
def template_save(request, pk):
    form_template = _template_for(request.user, pk, "design_form_template")
    draft = ensure_draft(form_template)
    form = TemplateMetaForm(
        request.POST,
        initial={
            "name": form_template.name,
            "description": form_template.description,
            "layout_notes": draft.layout_notes,
        },
    )
    if form.is_valid():
        form_template.name = form.cleaned_data["name"]
        form_template.description = form.cleaned_data["description"]
        draft.layout_notes = form.cleaned_data["layout_notes"]
        try:
            form_template.save()
            draft.save()
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
        else:
            messages.success(request, "Đã lưu bản nháp.")
    if getattr(request, "htmx", False):
        draft.refresh_from_db()
        return render(
            request,
            "formbuilder/partials/save_state.html",
            {
                "draft": draft,
                "save_label": saved_at_label(draft),
                "error": not form.is_valid(),
            },
        )
    return redirect("formbuilder:design", pk=form_template.pk)


@login_required
@require_GET
def template_preview(request, pk):
    form_template = _template_for(request.user, pk, "view_form_templates")
    draft = load_version(ensure_draft(form_template))
    form = DynamicEntryForm(
        None,
        None,
        version=draft,
        phieu=None,
        enforce_required=False,
    )
    return render(
        request,
        "formbuilder/preview.html",
        _preview_context(form_template, draft, form),
    )


@login_required
@require_POST
def template_preview_check(request, pk):
    form_template = _template_for(request.user, pk, "view_form_templates")
    draft = load_version(ensure_draft(form_template))
    form = DynamicEntryForm(
        request.POST,
        request.FILES,
        version=draft,
        phieu=None,
        enforce_required=True,
    )
    form.is_valid()
    return render(
        request,
        "formbuilder/preview.html",
        _preview_context(form_template, draft, form),
    )


def _preview_context(form_template, draft, form):
    fields = [
        field for section in draft.sections.all() for field in section.fields.all()
    ]
    visible, required = evaluate_rules(fields, list(draft.rules.all()), form.value_map)
    if form.is_bound:
        visible, required = form.visible, form.required_map
    sections = []
    for section in draft.sections.all():
        items = []
        for field in section.fields.all():
            if not visible.get(field.key, True):
                continue
            bound = form[field.key] if field.key in form.fields else None
            items.append(
                {
                    "field": field,
                    "bound": bound,
                    "required": required.get(field.key, field.required),
                    "span_class": f"form-span-{field.col_span}",
                }
            )
        sections.append({"section": section, "items": items})
    return {
        "form_template": form_template,
        "draft": draft,
        "sections": sections,
        "form": form,
    }


@login_required
@require_POST
def template_publish(request, pk):
    form_template = _template_for(request.user, pk, "publish_form_template")
    try:
        published = publish_template(form_template, request.user)
    except PublishError as exc:
        if getattr(request, "htmx", False):
            draft = ensure_draft(form_template)
            context = _builder_context(request, form_template, draft)
            context["publish_errors"] = exc.errors
            return render(
                request,
                "formbuilder/partials/stage.html",
                context,
                status=422,
            )
        return render(
            request,
            "formbuilder/partials/publish_checklist.html",
            {"errors": exc.errors, "form_template": form_template},
        )
    messages.success(request, f"Đã xuất bản phiên bản {published.version}.")
    if getattr(request, "htmx", False):
        return _render_builder(request, form_template)
    return redirect("formbuilder:design", pk=form_template.pk)


@login_required
@require_POST
def template_duplicate(request, pk):
    form_template = _template_for(request.user, pk, "publish_form_template")
    try:
        copy = duplicate_template(form_template, request.user)
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
        return redirect("formbuilder:list")
    messages.success(
        request,
        "Đã tạo bản sao ở trạng thái lưu trữ. Hãy lưu trữ biểu mẫu gốc trước khi khôi phục bản sao.",
    )
    return redirect("formbuilder:design", pk=copy.pk)


@login_required
@require_POST
def template_archive(request, pk):
    form_template = _template_for(request.user, pk, "archive_form_template")
    archive_template(form_template)
    messages.success(request, "Đã lưu trữ biểu mẫu. Phiếu cũ vẫn xem được.")
    return redirect("formbuilder:list")


@login_required
@require_POST
def template_restore(request, pk):
    form_template = _template_for(request.user, pk, "archive_form_template")
    try:
        restore_template(form_template)
    except (ValidationError, IntegrityError) as exc:
        messages.error(request, _error_text(exc))
        return redirect("formbuilder:list")
    messages.success(request, "Đã khôi phục biểu mẫu.")
    return redirect("formbuilder:design", pk=form_template.pk)


@login_required
@require_GET
def template_versions(request, pk):
    form_template = _template_for(request.user, pk, "view_form_templates")
    versions = form_template.versions.order_by("-version").select_related(
        "published_by"
    )
    rows = []
    for version in versions:
        rows.append(
            {
                "version": version,
                "field_count": version.fields.count(),
                "in_use": form_template.current_published_id == version.pk,
            }
        )
    return render(
        request,
        "formbuilder/versions.html",
        {
            "form_template": form_template,
            "rows": rows,
            "can_edit": can(
                request.user,
                "design_form_template",
                form_template.phong_id,
            ),
        },
    )


@login_required
@require_POST
def template_draft_from(request, pk, version_id):
    form_template = _template_for(request.user, pk, "design_form_template")
    version = get_object_or_404(
        FormTemplateVersion, pk=version_id, template=form_template
    )
    try:
        replace_draft_from(form_template, version)
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    else:
        messages.success(request, f"Đã tạo bản nháp từ phiên bản {version.version}.")
    return redirect("formbuilder:design", pk=form_template.pk)


@login_required
@require_POST
def section_create(request, pk):
    form_template = _template_for(request.user, pk, "design_form_template")
    draft = ensure_draft(form_template)
    title = (request.POST.get("title") or "Phần mới").strip()
    try:
        section = add_section(draft, title)
    except ValidationError as exc:
        return HttpResponseBadRequest(_error_text(exc))
    return _render_builder(request, form_template, section.fields.first() and None)


@login_required
@require_POST
def section_update(request, section_id):
    section = _load_child(request.user, FormSection, section_id, "design_form_template")
    form = SectionForm(request.POST)
    if form.is_valid():
        section.title = form.cleaned_data["title"]
        section.description = form.cleaned_data["description"]
        section.columns = form.cleaned_data["columns"]
        section.is_collapsible = form.cleaned_data["is_collapsible"]
        section.is_collapsed = form.cleaned_data["is_collapsed"]
        try:
            section.save()
        except ValidationError as exc:
            return HttpResponseBadRequest(_error_text(exc))
    return _render_builder(request, section.version.template)


@login_required
@require_POST
def section_delete(request, section_id):
    section = _load_child(request.user, FormSection, section_id, "design_form_template")
    template = section.version.template
    try:
        delete_section(section)
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return _render_builder(request, template)


@login_required
@require_POST
def section_duplicate(request, section_id):
    section = _load_child(request.user, FormSection, section_id, "design_form_template")
    try:
        duplicate_section(section)
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return _render_builder(request, section.version.template)


@login_required
@require_POST
def field_create(request, pk):
    form_template = _template_for(request.user, pk, "design_form_template")
    draft = ensure_draft(form_template)
    section_id = request.POST.get("section")
    section = draft.sections.order_by("order", "id").first()
    if section_id:
        section = get_object_or_404(FormSection, pk=section_id, version=draft)
    field_type = request.POST.get("field_type", "text")
    core_key = request.POST.get("core_key", "")
    try:
        if core_key:
            field = add_core_field(draft, section, core_key)
        else:
            field = add_field(draft, field_type, section)
    except ValidationError as exc:
        return HttpResponseBadRequest(_error_text(exc))
    return _render_builder(request, form_template, field.pk)


@login_required
@require_GET
def field_inspector(request, field_id):
    field = _load_child(request.user, FormField, field_id, "view_form_templates")
    return _render_builder(request, field.version.template, field.pk)


@login_required
@require_POST
def field_update(request, field_id):
    field = _load_child(request.user, FormField, field_id, "design_form_template")
    form = _inspector_form(field, request.POST)
    if form.is_valid():
        data = form.cleaned_data
        field.label = data["label"]
        field.required = data["required"]
        field.read_only = data["read_only"]
        field.placeholder = data["placeholder"]
        field.help_text = data["help_text"]
        field.default_value = data["default_value"]
        field.col_span = data["col_span"]
        field.is_hidden_by_default = data["is_hidden_by_default"]
        field.is_per_row = data["is_per_row"]
        field.min_value = data["min_value"]
        field.max_value = data["max_value"]
        field.min_length = data["min_length"]
        field.max_length = data["max_length"]
        field.regex = data["regex"]
        field.max_file_size_mb = data["max_file_size_mb"]
        field.allowed_extensions = data["allowed_extensions"]
        field.unique_within_form = data["unique_within_form"]
        field.catalog_source = data["catalog_source"]
        field.section = data["section"]
        try:
            field.save()
        except ValidationError as exc:
            form.add_error(None, _error_text(exc))
    if not form.is_valid():
        context = _builder_context(
            request,
            field.version.template,
            field.version,
            field.pk,
        )
        context["inspector_form"] = form
        template = (
            "formbuilder/partials/stage.html"
            if getattr(request, "htmx", False)
            else "formbuilder/design.html"
        )
        return render(request, template, context, status=422)
    return _render_builder(request, field.version.template, field.pk)


@login_required
@require_POST
def field_delete(request, field_id):
    field = _load_child(request.user, FormField, field_id, "design_form_template")
    template = field.version.template
    try:
        field.delete()
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return _render_builder(request, template)


@login_required
@require_POST
def template_reorder(request, pk):
    form_template = _template_for(request.user, pk, "design_form_template")
    draft = ensure_draft(form_template)
    try:
        if request.POST.get("field_id"):
            field = get_object_or_404(
                FormField, pk=request.POST.get("field_id"), version=draft
            )
            section_id = request.POST.get("section_id")
            move_field(
                field,
                direction=request.POST.get("direction"),
                section_id=int(section_id) if section_id else None,
            )
        elif request.POST.get("section_id"):
            section = get_object_or_404(
                FormSection,
                pk=request.POST.get("section_id"),
                version=draft,
            )
            move_section(section, request.POST.get("direction") or "down")
        else:
            payload = request.POST.get("payload") or request.body.decode() or "{}"
            if payload.startswith("{"):
                data = json.loads(payload)
            else:
                data = json.loads(request.POST.get("payload") or "{}")
            reorder(
                draft,
                [int(item) for item in data.get("sections", [])],
                [
                    {
                        "id": int(item["id"]),
                        "section_id": int(item["section_id"]),
                        "order": int(item["order"]),
                    }
                    for item in data.get("fields", [])
                ],
            )
    except (
        ValidationError,
        json.JSONDecodeError,
        KeyError,
        TypeError,
        ValueError,
    ) as exc:
        return HttpResponseBadRequest(
            _error_text(exc)
            if isinstance(exc, ValidationError)
            else "Thứ tự không hợp lệ."
        )
    return _render_builder(request, form_template)


@login_required
@require_POST
def option_create(request, field_id):
    field = _load_child(request.user, FormField, field_id, "design_form_template")
    form = OptionForm(request.POST)
    if form.is_valid():
        try:
            add_option(field, form.cleaned_data["label"], form.cleaned_data["value"])
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
    return _render_builder(request, field.version.template, field.pk)


@login_required
@require_POST
def option_delete(request, option_id):
    option = _load_child(
        request.user, FormFieldOption, option_id, "design_form_template"
    )
    field = option.field
    try:
        option.delete()
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return _render_builder(request, field.version.template, field.pk)


@login_required
@require_POST
def rule_create(request, pk):
    form_template = _template_for(request.user, pk, "design_form_template")
    draft = load_version(ensure_draft(form_template))
    form = _rule_form(draft, request.POST)
    if form.is_valid():
        order = draft.rules.count() + 1
        rule = FormRule(
            version=draft,
            source_field_key=form.cleaned_data["source_field_key"],
            operator=form.cleaned_data["operator"],
            compare_value=form.cleaned_data["compare_value"],
            action=form.cleaned_data["action"],
            target_field_key=form.cleaned_data["target_field_key"],
            order=order,
        )
        try:
            rule.save()
        except ValidationError as exc:
            messages.error(request, _error_text(exc))
    return _render_builder(request, form_template, request.POST.get("field_id"))


@login_required
@require_POST
def rule_delete(request, rule_id):
    rule = _load_child(request.user, FormRule, rule_id, "design_form_template")
    template = rule.version.template
    try:
        rule.delete()
    except ValidationError as exc:
        messages.error(request, _error_text(exc))
    return _render_builder(request, template)


@login_required
@require_GET
def attachment_download(request, attachment_id):
    attachment = get_object_or_404(
        FormAttachment.objects.select_related("value__response__phieu"),
        pk=attachment_id,
        value__response__phieu__in=scoped(
            request.user,
            PhieuNhapLieu.objects.all(),
            "phong_id",
        ),
    )
    handle = attachment.file.open("rb")
    return FileResponse(
        handle,
        as_attachment=True,
        filename=attachment.original_name,
    )
