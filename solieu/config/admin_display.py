"""Small HTML pills for the administration portal. Text is escaped."""

from django.utils.html import format_html

TONES = {
    "open": "pill pill-open",
    "locked": "pill pill-locked",
    "active": "pill pill-active",
    "inactive": "pill pill-inactive",
    "draft": "pill pill-draft",
    "confirmed": "pill pill-confirmed",
    "waiting": "pill pill-waiting",
    "returned": "pill pill-returned",
    "role-admin": "pill pill-role-admin",
    "role-center": "pill pill-role-center",
    "role-head": "pill pill-role-head",
    "role-entry": "pill pill-role-entry",
}

ROLE_TONE = {
    "system_admin": "role-admin",
    "center_head": "role-center",
    "department_head": "role-head",
    "entry_officer": "role-entry",
}


def pill(text, tone):
    css = TONES.get(tone, TONES["inactive"])
    return format_html('<span class="{}">{}</span>', css, text)
