"""Versioned form templates and the values entered against them.

Published versions are immutable. A phiếu keeps the version it first saved,
so a later publish does not change old submissions. Custom values are rows
in FormValue. JSON is used only for a multi-select list.
"""

import re

from django.conf import settings
from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import ValidatingModel
from apps.formbuilder.core import get_core_field

KEY_PATTERN = re.compile(r"^[a-zA-Z][a-zA-Z0-9_]*$")
CHOICE_FIELD_TYPES = frozenset({"select", "multi_select", "radio"})
PUBLISHED_LOCK_MESSAGE = "Phiên bản đã xuất bản không thể sửa."


class FunctionType(models.TextChoices):
    HOAT_DONG = "hoat_dong", "Hoạt động"
    CHI_TIEU = "chi_tieu", "Chỉ tiêu"
    DU_AN = "du_an", "Dự án"
    THANG = "thang", "Báo cáo tháng"


class VersionStatus(models.TextChoices):
    DRAFT = "draft", "Bản nháp"
    PUBLISHED = "published", "Đã xuất bản"
    ARCHIVED = "archived", "Đã lưu trữ"


class FieldType(models.TextChoices):
    TEXT = "text", "Văn bản ngắn"
    TEXTAREA = "textarea", "Văn bản dài"
    INTEGER = "integer", "Số nguyên"
    DECIMAL = "decimal", "Số thập phân"
    PERCENT = "percent", "Phần trăm"
    DATE = "date", "Ngày"
    TIME = "time", "Giờ"
    DATETIME = "datetime", "Ngày giờ"
    SELECT = "select", "Danh sách chọn"
    MULTI_SELECT = "multi_select", "Chọn nhiều"
    RADIO = "radio", "Chọn một"
    CHECKBOX = "checkbox", "Hộp kiểm"
    SWITCH = "switch", "Công tắc"
    EMAIL = "email", "Email"
    PHONE = "phone", "Số điện thoại"
    URL = "url", "Đường dẫn"
    FILE = "file", "Tệp"
    IMAGE = "image", "Hình ảnh"
    LOOKUP = "lookup", "Danh mục"
    INSTRUCTION = "instruction", "Hướng dẫn"


class FieldSource(models.TextChoices):
    CORE = "core", "Hệ thống"
    CUSTOM = "custom", "Tùy chỉnh"


class RuleOperator(models.TextChoices):
    EQUALS = "equals", "Bằng"
    NOT_EQUALS = "not_equals", "Khác"
    CONTAINS = "contains", "Chứa"
    IS_EMPTY = "is_empty", "Để trống"
    IS_NOT_EMPTY = "is_not_empty", "Có giá trị"
    GT = "gt", "Lớn hơn"
    GTE = "gte", "Lớn hơn hoặc bằng"
    LT = "lt", "Nhỏ hơn"
    LTE = "lte", "Nhỏ hơn hoặc bằng"
    IN = "in", "Thuộc"


class RuleAction(models.TextChoices):
    SHOW = "show", "Hiện"
    HIDE = "hide", "Ẩn"
    REQUIRE = "require", "Bắt buộc"
    OPTIONAL = "optional", "Không bắt buộc"


def build_scope_key(function_type, activity_type_id=None, group_id=None):
    """Return the stable scope key. Callers never edit it after create."""
    if function_type == FunctionType.HOAT_DONG:
        if activity_type_id:
            return f"hoat_dong:loai:{activity_type_id}"
        return "hoat_dong:*"
    if function_type == FunctionType.CHI_TIEU:
        if group_id:
            return f"chi_tieu:nhom:{group_id}"
        return "chi_tieu:*"
    if function_type == FunctionType.DU_AN:
        return "du_an:*"
    if function_type == FunctionType.THANG:
        return "thang:*"
    return ""


def _reject_unless_draft(version):
    """Reject edits unless the version row is still a draft.

    The status is read from the database so a stale in-memory object cannot
    keep writing after publish.
    """
    if version is None:
        return
    status = version.status
    if version.pk:
        status = (
            FormTemplateVersion.objects.filter(pk=version.pk)
            .values_list("status", flat=True)
            .first()
        )
    if status != VersionStatus.DRAFT:
        raise ValidationError(PUBLISHED_LOCK_MESSAGE)


class FormTemplate(ValidatingModel):
    phong = models.ForeignKey(
        "catalog.PhongBan",
        verbose_name="Phòng ban",
        on_delete=models.PROTECT,
        related_name="form_templates",
    )
    name = models.CharField("Tên biểu mẫu", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    function_type = models.CharField(
        "Chức năng",
        max_length=16,
        choices=FunctionType.choices,
    )
    target_activity_type = models.ForeignKey(
        "catalog.LoaiHoatDong",
        verbose_name="Loại hoạt động",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="form_templates",
    )
    target_indicator_group = models.ForeignKey(
        "catalog.NhomChiTieu",
        verbose_name="Nhóm chỉ tiêu",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="form_templates",
    )
    scope_key = models.CharField("Khóa phạm vi", max_length=80)
    is_active = models.BooleanField("Đang dùng", default=True)
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tạo",
        on_delete=models.PROTECT,
        related_name="form_templates_created",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)
    current_draft = models.ForeignKey(
        "FormTemplateVersion",
        verbose_name="Bản nháp hiện tại",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    current_published = models.ForeignKey(
        "FormTemplateVersion",
        verbose_name="Bản đã xuất bản",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="+",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Biểu mẫu"
        verbose_name_plural = "Biểu mẫu"
        ordering = ["phong", "name", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["phong", "scope_key"],
                condition=models.Q(is_active=True),
                name="formbuilder_template_active_scope_uniq",
                violation_error_message=(
                    "Đã có biểu mẫu đang hoạt động cho phạm vi này."
                ),
            )
        ]

    def __str__(self):
        return self.name

    def clean(self):
        super().clean()
        errors = {}
        self.name = (self.name or "").strip()
        if not self.name:
            errors["name"] = "Vui lòng nhập tên biểu mẫu."
        key = build_scope_key(
            self.function_type,
            self.target_activity_type_id,
            self.target_indicator_group_id,
        )
        if not key:
            errors["function_type"] = "Chức năng không hợp lệ."
        elif self.pk:
            previous = (
                FormTemplate.objects.filter(pk=self.pk)
                .values_list("scope_key", flat=True)
                .first()
            )
            if previous and previous != key:
                errors["scope_key"] = "Không thể đổi phạm vi của biểu mẫu."
            self.scope_key = previous or key
        else:
            self.scope_key = key

        activity_id = self.target_activity_type_id
        group_id = self.target_indicator_group_id
        if self.function_type == FunctionType.HOAT_DONG:
            if group_id:
                errors["target_indicator_group"] = (
                    "Biểu mẫu hoạt động không gắn nhóm chỉ tiêu."
                )
            if activity_id and self.target_activity_type.phong_id != self.phong_id:
                errors["target_activity_type"] = (
                    "Loại hoạt động phải thuộc phòng của biểu mẫu."
                )
        elif self.function_type == FunctionType.CHI_TIEU:
            if activity_id:
                errors["target_activity_type"] = (
                    "Biểu mẫu chỉ tiêu không gắn loại hoạt động."
                )
            if group_id and self.target_indicator_group.phong_id != self.phong_id:
                errors["target_indicator_group"] = (
                    "Nhóm chỉ tiêu phải thuộc phòng của biểu mẫu."
                )
        else:
            if activity_id:
                errors["target_activity_type"] = (
                    "Phạm vi này không dùng loại hoạt động."
                )
            if group_id:
                errors["target_indicator_group"] = (
                    "Phạm vi này không dùng nhóm chỉ tiêu."
                )
        if errors:
            raise ValidationError(errors)

    @property
    def scope_label(self):
        if self.target_activity_type_id:
            return str(self.target_activity_type)
        if self.target_indicator_group_id:
            return str(self.target_indicator_group)
        return "Tất cả"


class FormTemplateVersion(ValidatingModel):
    template = models.ForeignKey(
        FormTemplate,
        verbose_name="Biểu mẫu",
        on_delete=models.CASCADE,
        related_name="versions",
    )
    version = models.PositiveIntegerField("Phiên bản")
    status = models.CharField(
        "Trạng thái",
        max_length=16,
        choices=VersionStatus.choices,
        default=VersionStatus.DRAFT,
    )
    layout_notes = models.TextField("Ghi chú bố cục", blank=True)
    published_at = models.DateTimeField("Ngày xuất bản", null=True, blank=True)
    published_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người xuất bản",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="form_versions_published",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Phiên bản biểu mẫu"
        verbose_name_plural = "Phiên bản biểu mẫu"
        ordering = ["template", "version"]
        constraints = [
            models.UniqueConstraint(
                fields=["template", "version"],
                name="formbuilder_version_number_uniq",
            ),
            models.UniqueConstraint(
                fields=["template"],
                condition=models.Q(status=VersionStatus.PUBLISHED),
                name="formbuilder_one_published_version",
                violation_error_message=(
                    "Mỗi biểu mẫu chỉ có một phiên bản đang xuất bản."
                ),
            ),
        ]

    def __str__(self):
        return f"{self.template} v{self.version}"

    def save(self, *args, **kwargs):
        if self.pk:
            previous = (
                FormTemplateVersion.objects.filter(pk=self.pk)
                .values("status", "version", "layout_notes", "template_id")
                .first()
            )
            if previous and previous["status"] != VersionStatus.DRAFT:
                archiving = (
                    previous["status"] == VersionStatus.PUBLISHED
                    and self.status == VersionStatus.ARCHIVED
                    and self.version == previous["version"]
                    and self.layout_notes == previous["layout_notes"]
                    and self.template_id == previous["template_id"]
                )
                if not archiving:
                    raise ValidationError(PUBLISHED_LOCK_MESSAGE)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.status != VersionStatus.DRAFT:
            raise ValidationError("Không thể xóa phiên bản đã xuất bản.")
        if self.responses.exists():
            raise ValidationError("Không thể xóa phiên bản đã có phiếu.")
        return super().delete(*args, **kwargs)


class FormSection(ValidatingModel):
    version = models.ForeignKey(
        FormTemplateVersion,
        verbose_name="Phiên bản",
        on_delete=models.CASCADE,
        related_name="sections",
    )
    title = models.CharField("Tiêu đề", max_length=255)
    description = models.TextField("Mô tả", blank=True)
    order = models.PositiveIntegerField("Thứ tự", default=1)
    columns = models.PositiveSmallIntegerField(
        "Số cột",
        default=1,
        validators=[MinValueValidator(1), MaxValueValidator(4)],
    )
    is_collapsible = models.BooleanField("Cho phép thu gọn", default=False)
    is_collapsed = models.BooleanField("Thu gọn ban đầu", default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Phần biểu mẫu"
        verbose_name_plural = "Phần biểu mẫu"
        ordering = ["order", "id"]

    def __str__(self):
        return self.title

    def clean(self):
        super().clean()
        self.title = (self.title or "").strip()
        if not self.title:
            raise ValidationError({"title": "Vui lòng nhập tiêu đề phần."})
        if self.order < 1:
            raise ValidationError({"order": "Thứ tự phải lớn hơn 0."})

    def save(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        return super().delete(*args, **kwargs)


class FormField(ValidatingModel):
    version = models.ForeignKey(
        FormTemplateVersion,
        verbose_name="Phiên bản",
        on_delete=models.CASCADE,
        related_name="fields",
    )
    section = models.ForeignKey(
        FormSection,
        verbose_name="Phần",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="fields",
    )
    key = models.SlugField("Mã trường", max_length=80)
    label = models.CharField("Nhãn", max_length=255)
    field_type = models.CharField(
        "Kiểu dữ liệu",
        max_length=20,
        choices=FieldType.choices,
    )
    source = models.CharField(
        "Nguồn",
        max_length=8,
        choices=FieldSource.choices,
        default=FieldSource.CUSTOM,
    )
    core_key = models.CharField("Mã hệ thống", max_length=80, blank=True)
    required = models.BooleanField("Bắt buộc", default=False)
    read_only = models.BooleanField("Chỉ đọc", default=False)
    default_value = models.TextField("Giá trị mặc định", blank=True)
    placeholder = models.CharField("Gợi ý nhập", max_length=255, blank=True)
    help_text = models.TextField("Trợ giúp", blank=True)
    order = models.PositiveIntegerField("Thứ tự", default=1)
    col_span = models.PositiveSmallIntegerField(
        "Độ rộng",
        default=12,
        validators=[MinValueValidator(1), MaxValueValidator(12)],
    )
    is_hidden_by_default = models.BooleanField("Ẩn mặc định", default=False)
    is_per_row = models.BooleanField("Theo từng dòng chỉ tiêu", default=False)
    min_value = models.DecimalField(
        "Giá trị nhỏ nhất",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    max_value = models.DecimalField(
        "Giá trị lớn nhất",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    min_length = models.PositiveIntegerField(
        "Độ dài nhỏ nhất",
        null=True,
        blank=True,
    )
    max_length = models.PositiveIntegerField(
        "Độ dài lớn nhất",
        null=True,
        blank=True,
    )
    regex = models.CharField("Biểu thức chính quy", max_length=255, blank=True)
    max_file_size_mb = models.PositiveIntegerField(
        "Dung lượng tối đa (MB)",
        null=True,
        blank=True,
    )
    allowed_extensions = models.CharField(
        "Phần mở rộng cho phép",
        max_length=255,
        blank=True,
    )
    unique_within_form = models.BooleanField(
        "Không trùng trong biểu mẫu",
        default=False,
    )
    catalog_source = models.CharField("Nguồn danh mục", max_length=40, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Trường biểu mẫu"
        verbose_name_plural = "Trường biểu mẫu"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["version", "key"],
                name="formbuilder_field_key_uniq",
                violation_error_message="Mã trường bị trùng trong phiên bản.",
            )
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        errors = {}
        self.label = (self.label or "").strip()
        self.key = (self.key or "").strip()
        self.core_key = (self.core_key or "").strip()
        if self.allowed_extensions:
            parts = [
                part.strip().lower().lstrip(".")
                for part in self.allowed_extensions.split(",")
                if part.strip()
            ]
            self.allowed_extensions = ",".join(parts)
        if not self.label:
            errors["label"] = "Vui lòng nhập nhãn trường."
        if not KEY_PATTERN.match(self.key or ""):
            errors["key"] = (
                "Mã trường phải bắt đầu bằng chữ và chỉ gồm chữ, số, dấu gạch dưới."
            )
        if not self.section_id:
            errors["section"] = "Trường phải thuộc một phần."
        elif self.version_id and self.section.version_id != self.version_id:
            errors["section"] = "Trường phải thuộc một phần của cùng phiên bản."
        if self.order < 1:
            errors["order"] = "Thứ tự phải lớn hơn 0."
        if self.min_value is not None and self.max_value is not None:
            if self.min_value > self.max_value:
                errors["min_value"] = (
                    "Giá trị nhỏ nhất không được lớn hơn giá trị lớn nhất."
                )
        if self.min_length is not None and self.max_length is not None:
            if self.min_length > self.max_length:
                errors["min_length"] = (
                    "Độ dài nhỏ nhất không được lớn hơn độ dài lớn nhất."
                )
        if self.regex:
            try:
                re.compile(self.regex)
            except re.error:
                errors["regex"] = "Biểu thức chính quy không hợp lệ."
        if self.pk:
            previous_key = (
                FormField.objects.filter(pk=self.pk)
                .values_list("key", flat=True)
                .first()
            )
            if previous_key and previous_key != self.key:
                errors["key"] = "Không thể đổi mã trường sau khi tạo."

        function_type = None
        if self.version_id:
            function_type = self.version.template.function_type
        if self.is_per_row and function_type != FunctionType.CHI_TIEU:
            errors["is_per_row"] = "Chỉ biểu mẫu chỉ tiêu mới có trường theo dòng."
        if (
            function_type == FunctionType.CHI_TIEU
            and self.source == FieldSource.CUSTOM
            and not self.is_per_row
        ):
            errors["is_per_row"] = (
                "Trường tùy chỉnh của biểu mẫu chỉ tiêu phải nhập theo từng dòng."
            )
        if self.source == FieldSource.CUSTOM:
            if self.core_key:
                errors["core_key"] = "Trường tùy chỉnh không có mã hệ thống."
            if self.key and not self.key.startswith("cf_"):
                errors["key"] = "Mã trường tùy chỉnh phải bắt đầu bằng cf_."
        elif self.source == FieldSource.CORE:
            definition = get_core_field(function_type, self.core_key)
            if definition is None:
                errors["core_key"] = "Trường hệ thống không thuộc chức năng này."
            else:
                if self.field_type != definition.field_type:
                    errors["field_type"] = "Không thể đổi kiểu trường hệ thống."
                if self.key != definition.key:
                    errors["key"] = "Không thể đổi mã trường hệ thống."
                if definition.required and not self.required:
                    errors["required"] = "Không thể bỏ bắt buộc của trường hệ thống."
                if definition.required and self.is_hidden_by_default:
                    errors["is_hidden_by_default"] = (
                        "Không thể ẩn trường hệ thống bắt buộc."
                    )
        if self.field_type == FieldType.LOOKUP and self.source == FieldSource.CUSTOM:
            from apps.formbuilder.lookups import CATALOG_KEYS

            if self.catalog_source not in CATALOG_KEYS:
                errors["catalog_source"] = "Chọn một danh mục trong danh sách cho phép."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        if self.source == FieldSource.CORE and self.version_id:
            definition = get_core_field(
                self.version.template.function_type,
                self.core_key,
            )
            if definition is not None and definition.required:
                raise ValidationError("Không thể xóa trường hệ thống bắt buộc.")
        return super().delete(*args, **kwargs)

    @property
    def is_choice(self):
        return self.field_type in CHOICE_FIELD_TYPES


class FormFieldOption(ValidatingModel):
    field = models.ForeignKey(
        FormField,
        verbose_name="Trường",
        on_delete=models.CASCADE,
        related_name="options",
    )
    label = models.CharField("Nhãn", max_length=255)
    value = models.CharField("Giá trị", max_length=100)
    order = models.PositiveIntegerField("Thứ tự", default=1)
    is_active = models.BooleanField("Đang dùng", default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Lựa chọn"
        verbose_name_plural = "Lựa chọn"
        ordering = ["order", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["field", "value"],
                name="formbuilder_option_value_uniq",
                violation_error_message="Giá trị lựa chọn bị trùng.",
            )
        ]

    def __str__(self):
        return self.label

    def clean(self):
        super().clean()
        self.label = (self.label or "").strip()
        self.value = (self.value or "").strip()
        if not self.label:
            raise ValidationError({"label": "Vui lòng nhập nhãn lựa chọn."})
        if not self.value:
            raise ValidationError({"value": "Vui lòng nhập giá trị lựa chọn."})

    def save(self, *args, **kwargs):
        if self.field_id:
            _reject_unless_draft(self.field.version)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.field_id:
            _reject_unless_draft(self.field.version)
        return super().delete(*args, **kwargs)


class FormRule(ValidatingModel):
    version = models.ForeignKey(
        FormTemplateVersion,
        verbose_name="Phiên bản",
        on_delete=models.CASCADE,
        related_name="rules",
    )
    source_field_key = models.CharField("Trường nguồn", max_length=80)
    operator = models.CharField(
        "Phép so sánh",
        max_length=16,
        choices=RuleOperator.choices,
    )
    compare_value = models.TextField("Giá trị so sánh", blank=True)
    action = models.CharField(
        "Hành động",
        max_length=16,
        choices=RuleAction.choices,
    )
    target_field_key = models.CharField("Trường đích", max_length=80)
    order = models.PositiveIntegerField("Thứ tự", default=1)
    is_active = models.BooleanField("Đang dùng", default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Điều kiện"
        verbose_name_plural = "Điều kiện"
        ordering = ["order", "id"]

    def __str__(self):
        return f"{self.source_field_key} → {self.target_field_key}"

    def clean(self):
        super().clean()
        from apps.formbuilder.validators import operator_allowed

        errors = {}
        if self.source_field_key == self.target_field_key:
            errors["target_field_key"] = (
                "Điều kiện không được trỏ vào chính trường nguồn."
            )
        if self.version_id:
            fields = {field.key: field for field in self.version.fields.all()}
            source = fields.get(self.source_field_key)
            target = fields.get(self.target_field_key)
            if source is None:
                errors["source_field_key"] = (
                    "Trường nguồn không có trong phiên bản này."
                )
            elif not operator_allowed(source.field_type, self.operator):
                errors["operator"] = "Phép so sánh không dùng được với kiểu trường này."
            if target is None:
                errors["target_field_key"] = "Trường đích không có trong phiên bản này."
            elif target.field_type == FieldType.INSTRUCTION and self.action in {
                RuleAction.REQUIRE,
                RuleAction.OPTIONAL,
            }:
                errors["action"] = "Dòng hướng dẫn không có trạng thái bắt buộc."
            elif target is not None and target.source == FieldSource.CORE:
                definition = get_core_field(
                    self.version.template.function_type,
                    target.core_key,
                )
                if (
                    definition
                    and definition.required
                    and self.action
                    in {
                        RuleAction.HIDE,
                        RuleAction.OPTIONAL,
                    }
                ):
                    errors["action"] = (
                        "Không thể ẩn hoặc bỏ bắt buộc trường hệ thống bắt buộc."
                    )
        if self.order < 1:
            errors["order"] = "Thứ tự phải lớn hơn 0."
        if errors:
            raise ValidationError(errors)

    def save(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        return super().save(*args, **kwargs)

    def delete(self, *args, **kwargs):
        if self.version_id:
            _reject_unless_draft(self.version)
        return super().delete(*args, **kwargs)


class FormResponse(ValidatingModel):
    phieu = models.ForeignKey(
        "entry.PhieuNhapLieu",
        verbose_name="Phiếu nhập liệu",
        on_delete=models.CASCADE,
        related_name="form_responses",
    )
    template = models.ForeignKey(
        FormTemplate,
        verbose_name="Biểu mẫu",
        on_delete=models.PROTECT,
        related_name="responses",
    )
    template_version = models.ForeignKey(
        FormTemplateVersion,
        verbose_name="Phiên bản",
        on_delete=models.PROTECT,
        related_name="responses",
    )
    created_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người tạo",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="form_responses_created",
    )
    updated_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người cập nhật",
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name="form_responses_updated",
    )
    created_at = models.DateTimeField("Ngày tạo", auto_now_add=True)
    updated_at = models.DateTimeField("Ngày cập nhật", auto_now=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Bản trả lời"
        verbose_name_plural = "Bản trả lời"
        ordering = ["-id"]
        constraints = [
            models.UniqueConstraint(
                fields=["phieu", "template"],
                name="formbuilder_response_phieu_template_uniq",
            )
        ]

    def __str__(self):
        return f"{self.phieu} — {self.template_version}"

    def clean(self):
        super().clean()
        if (
            self.template_id
            and self.template_version_id
            and self.template_version.template_id != self.template_id
        ):
            raise ValidationError(
                {"template_version": "Phiên bản không thuộc biểu mẫu này."}
            )


class FormValue(ValidatingModel):
    response = models.ForeignKey(
        FormResponse,
        verbose_name="Bản trả lời",
        on_delete=models.CASCADE,
        related_name="values",
    )
    field = models.ForeignKey(
        FormField,
        verbose_name="Trường",
        on_delete=models.PROTECT,
        related_name="values",
    )
    field_key = models.CharField("Mã trường", max_length=80)
    so_lieu = models.ForeignKey(
        "entry.SoLieu",
        verbose_name="Dòng số liệu",
        null=True,
        blank=True,
        on_delete=models.CASCADE,
        related_name="form_values",
    )
    value_text = models.TextField("Giá trị chữ", blank=True)
    value_number = models.DecimalField(
        "Giá trị số",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    value_date = models.DateField("Giá trị ngày", null=True, blank=True)
    value_time = models.TimeField("Giá trị giờ", null=True, blank=True)
    value_datetime = models.DateTimeField("Giá trị ngày giờ", null=True, blank=True)
    value_bool = models.BooleanField("Giá trị đúng/sai", null=True, blank=True)
    value_json = models.JSONField("Giá trị danh sách", null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Giá trị biểu mẫu"
        verbose_name_plural = "Giá trị biểu mẫu"
        constraints = [
            models.UniqueConstraint(
                fields=["response", "field"],
                condition=models.Q(so_lieu__isnull=True),
                name="formbuilder_value_form_uniq",
            ),
            models.UniqueConstraint(
                fields=["response", "field", "so_lieu"],
                condition=models.Q(so_lieu__isnull=False),
                name="formbuilder_value_row_uniq",
            ),
        ]

    def __str__(self):
        return self.field_key


class FormAttachment(models.Model):
    value = models.ForeignKey(
        FormValue,
        verbose_name="Giá trị",
        on_delete=models.CASCADE,
        related_name="attachments",
    )
    file = models.FileField("Tệp", upload_to="form_uploads/%Y/%m/")
    original_name = models.CharField("Tên tệp gốc", max_length=255)
    content_type = models.CharField("Kiểu nội dung", max_length=100, blank=True)
    size = models.PositiveBigIntegerField("Dung lượng")
    uploaded_at = models.DateTimeField("Ngày tải lên", auto_now_add=True)

    class Meta:
        verbose_name = "Tệp đính kèm"
        verbose_name_plural = "Tệp đính kèm"

    def __str__(self):
        return self.original_name
