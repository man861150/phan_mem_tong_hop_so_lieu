"""URL routes for activities."""

from django.urls import path

from apps.activities.views import (
    don_vi_them,
    du_an_create,
    du_an_detail,
    du_an_list,
    hoat_dong_create,
    hoat_dong_da_to_chuc,
    hoat_dong_detail,
    hoat_dong_list,
)

app_name = "activities"

urlpatterns = [
    path("hoat-dong/", hoat_dong_list, name="hoat_dong_list"),
    path("hoat-dong/tao/", hoat_dong_create, name="hoat_dong_create"),
    path(
        "hoat-dong/don-vi/them/",
        don_vi_them,
        name="don_vi_them",
    ),
    path(
        "hoat-dong/<int:pk>/da-to-chuc/",
        hoat_dong_da_to_chuc,
        name="hoat_dong_da_to_chuc",
    ),
    path("hoat-dong/<int:pk>/", hoat_dong_detail, name="hoat_dong_detail"),
    path("du-an/", du_an_list, name="du_an_list"),
    path("du-an/tao/", du_an_create, name="du_an_create"),
    path("du-an/<int:pk>/", du_an_detail, name="du_an_detail"),
]
