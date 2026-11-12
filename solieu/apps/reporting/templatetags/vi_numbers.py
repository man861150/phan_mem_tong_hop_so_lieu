"""Template filters for Vietnamese number display."""

from django import template

from apps.reporting.formatting import format_vi_number

register = template.Library()


@register.filter
def vi_number(value):
    """Render a stored number with Vietnamese grouping."""
    return format_vi_number(value)
