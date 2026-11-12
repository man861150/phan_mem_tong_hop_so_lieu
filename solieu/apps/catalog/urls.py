"""URL routes for catalog."""

from django.urls import path

from apps.catalog.views import danh_muc, ke_hoach

app_name = "catalog"

urlpatterns = [
    path("danh-muc/", danh_muc, name="danh_muc"),
    path("ke-hoach/<int:nam>/", ke_hoach, name="ke_hoach"),
]
