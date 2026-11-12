"""Navigation entries derived from the permission matrix."""

from django.urls import reverse

from apps.accounts.permissions import can


def _can_any(user, *actions) -> bool:
    return any(can(user, action) for action in actions)


def navigation(request):
    """Return links the signed-in role may use, in display order."""
    user = getattr(request, "user", None)
    if not getattr(user, "is_authenticated", False):
        return {"navigation": []}

    path = request.path
    home_url = reverse("home")
    items = [
        {
            "label": "Trang chủ",
            "url": home_url,
            "active": path == home_url,
            "visible": can(user, "view_progress"),
        },
        {
            "label": "Hoạt động",
            "url": reverse("activities:hoat_dong_list"),
            "active": path.startswith("/hoat-dong/")
            or path.startswith("/phieu/hoat-dong/"),
            "visible": _can_any(user, "edit_entry", "view_progress"),
        },
        {
            "label": "Dự án",
            "url": reverse("activities:du_an_list"),
            "active": path.startswith("/du-an/")
            or path.startswith("/phieu/du-an/"),
            "visible": _can_any(user, "edit_entry", "view_progress"),
        },
        {
            "label": "Duyệt",
            "url": reverse("entry:duyet_list"),
            "active": path.startswith("/duyet/"),
            "visible": can(user, "approve_entry"),
        },
        {
            "label": "Tiến độ",
            "url": reverse("reporting:tien_do"),
            "active": path.startswith("/tien-do/"),
            "visible": can(user, "view_progress"),
        },
        {
            "label": "Báo cáo",
            "url": reverse("reporting:bao_cao"),
            "active": path.startswith("/bao-cao/"),
            "visible": _can_any(
                user,
                "view_progress",
                "export_department_report",
                "export_center_report",
            ),
        },
        {
            "label": "Lịch sử",
            "url": reverse("reporting:lich_su"),
            "active": path.startswith("/lich-su/"),
            "visible": can(user, "view_history"),
        },
        {
            "label": "Danh mục",
            "url": reverse("catalog:danh_muc"),
            "active": path.startswith("/danh-muc/")
            or path.startswith("/ke-hoach/"),
            "visible": can(user, "view_catalog"),
        },
        {
            "label": "Quản trị",
            "url": reverse("admin:index"),
            "active": path.startswith("/admin/"),
            "visible": _can_any(
                user,
                "manage_users",
                "manage_catalog",
                "manage_periods",
            )
            and user.is_staff,
        },
    ]
    return {"navigation": items}
