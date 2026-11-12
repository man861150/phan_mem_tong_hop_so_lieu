"""URL routes for entry."""

from django.urls import path

from apps.entry.views import (
    phieu_du_an,
    phieu_hoat_dong,
    phieu_hoat_dong_bo_sung,
    phieu_thang,
    phieu_xoa,
)

app_name = "entry"

urlpatterns = [
    path(
        "phieu/hoat-dong/<int:hoat_dong_id>/",
        phieu_hoat_dong,
        name="phieu_hoat_dong",
    ),
    path(
        "phieu/hoat-dong/<int:hoat_dong_id>/bo-sung/",
        phieu_hoat_dong_bo_sung,
        name="phieu_hoat_dong_bo_sung",
    ),
    path("phieu/thang/<int:ky_id>/", phieu_thang, name="phieu_thang"),
    path("phieu/du-an/<int:du_an_id>/", phieu_du_an, name="phieu_du_an"),
    path("phieu/<int:phieu_id>/xoa/", phieu_xoa, name="phieu_xoa"),
]
