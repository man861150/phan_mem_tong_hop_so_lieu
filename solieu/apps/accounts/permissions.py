"""The only permission check in the project. Call can() before every write."""

from apps.accounts.roles import SCOPED_ROLES, Role

# department_head includes every entry_officer action inside the same department.
_ENTRY_OFFICER_ACTIONS = frozenset(
    {
        "edit_entry",
        "view_progress",
        "export_department_report",
        "view_history",
    }
)

_ALLOWED = {
    Role.ENTRY_OFFICER: _ENTRY_OFFICER_ACTIONS,
    Role.DEPARTMENT_HEAD: _ENTRY_OFFICER_ACTIONS
    | frozenset(
        {
            "view_catalog",
            "confirm_plan",
            "view_plan",
            "approve_entry",
            "view_form_templates",
            "design_form_template",
            "publish_form_template",
            "archive_form_template",
        }
    ),
    Role.CENTER_HEAD: frozenset(
        {
            "view_plan",
            "view_progress",
            "export_department_report",
            "export_center_report",
            "view_history",
            "view_form_templates",
        }
    ),
    Role.SYSTEM_ADMIN: frozenset(
        {
            "manage_users",
            "manage_catalog",
            "view_catalog",
            "edit_plan",
            "view_plan",
            "manage_periods",
            "view_progress",
            "export_department_report",
            "export_center_report",
            "view_history",
            "view_form_templates",
            "design_form_template",
            "publish_form_template",
            "archive_form_template",
        }
    ),
}


def can(user, action, phong_id=None) -> bool:
    """Return whether user may perform action, optionally inside one department.

    phong_id is omitted for a role-level check. A scoped role is refused when
    the target department is not theirs, and when they have no department.
    Center head and system admin are not filtered by phong_id.
    """
    if not getattr(user, "is_authenticated", False):
        return False
    if not getattr(user, "is_active", False):
        return False
    allowed = _ALLOWED.get(getattr(user, "role", None))
    if allowed is None or action not in allowed:
        return False
    if user.role in SCOPED_ROLES:
        if user.phong_id is None:
            return False
        if phong_id is not None and phong_id != user.phong_id:
            return False
    return True
