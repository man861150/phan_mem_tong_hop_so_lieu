from django.contrib import admin
from django.urls import include, path

from config.views import home

admin.site.site_header = "Quản trị tổng hợp số liệu"
admin.site.site_title = "Tổng hợp số liệu"
admin.site.index_title = "Danh mục hệ thống"

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("accounts/", include("apps.accounts.urls")),
    path("catalog/", include("apps.catalog.urls")),
    path("activities/", include("apps.activities.urls")),
    path("entry/", include("apps.entry.urls")),
    path("reporting/", include("apps.reporting.urls")),
]
