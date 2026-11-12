from django.conf import settings
from django.conf.urls.static import static
from django.contrib import admin
from django.urls import include, path

from config.views import home

admin.site.site_header = "Quản trị tổng hợp số liệu"
admin.site.site_title = "Tổng hợp số liệu"
admin.site.index_title = "Danh mục hệ thống"

urlpatterns = [
    path("", home, name="home"),
    path("admin/", admin.site.urls),
    path("", include("apps.accounts.urls")),
    path("", include("apps.catalog.urls")),
    path("", include("apps.activities.urls")),
    path("", include("apps.entry.urls")),
    path("", include("apps.reporting.urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
