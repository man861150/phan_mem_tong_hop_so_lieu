"""Server-side checks for rules, files, and publish."""

import re
from collections import defaultdict

from django.core.exceptions import ValidationError
from django.core.validators import URLValidator, validate_email

PHONE_PATTERN = re.compile(r"^(?:\+84|0)\d{9,10}$")
IMAGE_EXTENSIONS = frozenset({"jpg", "jpeg", "png", "gif", "webp"})
MAX_FILE_MB = 25

TEXT_OPERATORS = frozenset(
    {"equals", "not_equals", "contains", "is_empty", "is_not_empty", "in"}
)
NUMBER_OPERATORS = frozenset(
    {
        "equals",
        "not_equals",
        "gt",
        "gte",
        "lt",
        "lte",
        "is_empty",
        "is_not_empty",
        "in",
    }
)
BOOL_OPERATORS = frozenset({"equals", "not_equals", "is_empty", "is_not_empty"})
DATE_OPERATORS = NUMBER_OPERATORS - {"in"}
MULTI_OPERATORS = frozenset({"equals", "contains", "is_empty", "is_not_empty", "in"})
FILE_OPERATORS = frozenset({"is_empty", "is_not_empty"})
EMPTY_OPERATORS = frozenset({"is_empty", "is_not_empty"})

OPERATORS_BY_TYPE = {
    "text": TEXT_OPERATORS,
    "textarea": TEXT_OPERATORS,
    "email": TEXT_OPERATORS,
    "phone": TEXT_OPERATORS,
    "url": TEXT_OPERATORS,
    "select": TEXT_OPERATORS,
    "radio": TEXT_OPERATORS,
    "lookup": TEXT_OPERATORS,
    "integer": NUMBER_OPERATORS,
    "decimal": NUMBER_OPERATORS,
    "percent": NUMBER_OPERATORS,
    "date": DATE_OPERATORS,
    "time": DATE_OPERATORS,
    "datetime": DATE_OPERATORS,
    "checkbox": BOOL_OPERATORS,
    "switch": BOOL_OPERATORS,
    "multi_select": MULTI_OPERATORS,
    "file": FILE_OPERATORS,
    "image": FILE_OPERATORS,
    "instruction": EMPTY_OPERATORS,
}


def operator_allowed(field_type, operator):
    return operator in OPERATORS_BY_TYPE.get(field_type, EMPTY_OPERATORS)


def normalize_phone(value):
    text = (value or "").strip().replace(" ", "").replace(".", "")
    if not PHONE_PATTERN.match(text):
        raise ValidationError("Số điện thoại không hợp lệ.")
    return text


def compile_regex(pattern):
    try:
        return re.compile(pattern)
    except re.error as exc:
        raise ValidationError("Biểu thức chính quy không hợp lệ.") from exc


def extension_of(name):
    base = (name or "").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    if "." not in base:
        return ""
    return base.rsplit(".", 1)[-1].lower()


def parse_extensions(raw):
    return [
        part.strip().lower().lstrip(".")
        for part in (raw or "").split(",")
        if part.strip()
    ]


def validate_upload(upload, field):
    """Reject empty files, oversize files, and extensions outside the list."""
    if upload is None:
        return
    size = getattr(upload, "size", 0) or 0
    if size <= 0:
        raise ValidationError("Tệp tải lên đang trống.")
    limit = field.max_file_size_mb or MAX_FILE_MB
    if limit > MAX_FILE_MB:
        limit = MAX_FILE_MB
    if size > limit * 1024 * 1024:
        raise ValidationError(f"Tệp vượt quá {limit} MB.")
    allowed = parse_extensions(field.allowed_extensions)
    if field.field_type == "image":
        allowed = [item for item in allowed if item in IMAGE_EXTENSIONS] or list(
            IMAGE_EXTENSIONS
        )
    if not allowed:
        raise ValidationError("Chưa khai báo phần mở rộng được phép.")
    ext = extension_of(getattr(upload, "name", ""))
    if ext not in allowed:
        raise ValidationError("Phần mở rộng của tệp không được phép.")
    content_type = getattr(upload, "content_type", "") or ""
    if (
        field.field_type == "image"
        and content_type
        and not content_type.startswith("image/")
    ):
        raise ValidationError("Tệp không phải hình ảnh.")


def sanitize_filename(name):
    base = (name or "tep").rsplit("/", 1)[-1].rsplit("\\", 1)[-1]
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "_", base).strip("._")
    return (cleaned or "tep")[:255]


def validate_email_value(value):
    validate_email(value)


def validate_url_value(value):
    URLValidator()(value)


def has_cycle(rules):
    """Return True when active rules form a dependency cycle."""
    graph = defaultdict(set)
    for rule in rules:
        if not rule.is_active:
            continue
        if rule.source_field_key == rule.target_field_key:
            return True
        graph[rule.source_field_key].add(rule.target_field_key)
    visiting = set()
    visited = set()

    def walk(node):
        if node in visiting:
            return True
        if node in visited:
            return False
        visiting.add(node)
        for child in graph.get(node, ()):
            if walk(child):
                return True
        visiting.remove(node)
        visited.add(node)
        return False

    return any(walk(node) for node in list(graph))
