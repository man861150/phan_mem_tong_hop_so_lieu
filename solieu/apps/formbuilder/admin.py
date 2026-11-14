"""Read-only admin registration for support. The designer is the real UI."""

from django.contrib import admin

from apps.formbuilder.models import (
    FormAttachment,
    FormField,
    FormFieldOption,
    FormResponse,
    FormRule,
    FormSection,
    FormTemplate,
    FormTemplateVersion,
    FormValue,
)


class ReadOnlyAdmin(admin.ModelAdmin):
    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return False


class FormSectionInline(admin.TabularInline):
    model = FormSection
    extra = 0
    can_delete = False

    def has_add_permission(self, request, obj=None):
        return False

    def has_change_permission(self, request, obj=None):
        return False


@admin.register(FormTemplate)
class FormTemplateAdmin(ReadOnlyAdmin):
    list_display = ("name", "phong", "function_type", "scope_key", "is_active")
    list_filter = ("function_type", "is_active")
    search_fields = ("name", "scope_key", "phong__ma_phong")


@admin.register(FormTemplateVersion)
class FormTemplateVersionAdmin(ReadOnlyAdmin):
    list_display = ("template", "version", "status", "published_at", "published_by")
    list_filter = ("status",)
    inlines = [FormSectionInline]


@admin.register(FormField)
class FormFieldAdmin(ReadOnlyAdmin):
    list_display = ("label", "key", "field_type", "source", "version")
    search_fields = ("label", "key")


@admin.register(FormFieldOption)
class FormFieldOptionAdmin(ReadOnlyAdmin):
    list_display = ("label", "value", "field", "is_active")


@admin.register(FormRule)
class FormRuleAdmin(ReadOnlyAdmin):
    list_display = (
        "version",
        "source_field_key",
        "operator",
        "action",
        "target_field_key",
        "is_active",
    )


@admin.register(FormResponse)
class FormResponseAdmin(ReadOnlyAdmin):
    list_display = ("phieu", "template", "template_version", "updated_at")


@admin.register(FormValue)
class FormValueAdmin(ReadOnlyAdmin):
    list_display = ("response", "field_key", "so_lieu")


@admin.register(FormAttachment)
class FormAttachmentAdmin(ReadOnlyAdmin):
    list_display = ("original_name", "size", "uploaded_at")
