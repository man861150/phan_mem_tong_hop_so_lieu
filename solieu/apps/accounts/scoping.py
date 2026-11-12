"""The only department queryset filter. This helper never grants write access."""

from apps.accounts.roles import SCOPED_ROLES, Role

_UNSCOPED_ROLES = frozenset({Role.CENTER_HEAD, Role.SYSTEM_ADMIN})


def scoped(user, queryset, phong_field="phong_id"):
    """Limit queryset to the caller's department.

    center_head and system_admin receive the queryset unchanged. A scoped role
    with no department receives an empty queryset. Pass phong_field="id" when
    the queryset is PhongBan itself.
    """
    if not getattr(user, "is_authenticated", False):
        return queryset.none()
    role = getattr(user, "role", None)
    if role in _UNSCOPED_ROLES:
        return queryset
    if role in SCOPED_ROLES:
        if not user.phong_id:
            return queryset.none()
        return queryset.filter(**{phong_field: user.phong_id})
    return queryset.none()
