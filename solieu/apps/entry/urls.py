"""URL routes for entry."""

from django.urls import path

from apps.entry.views import (
    duyet_list,
    phieu_detail,
    phieu_du_an,
    phieu_duyet,
    phieu_gui,
    phieu_hoat_dong,
    phieu_hoat_dong_bo_sung,
    phieu_mo_lai,
    phieu_thang,
    phieu_tra_lai,
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
    path("duyet/", duyet_list, name="duyet_list"),
    path("phieu/<int:phieu_id>/", phieu_detail, name="phieu_detail"),
    path("phieu/<int:phieu_id>/gui/", phieu_gui, name="phieu_gui"),
    path("phieu/<int:phieu_id>/duyet/", phieu_duyet, name="phieu_duyet"),
    path(
        "phieu/<int:phieu_id>/tra-lai/",
        phieu_tra_lai,
        name="phieu_tra_lai",
    ),
    path(
        "phieu/<int:phieu_id>/mo-lai/",
        phieu_mo_lai,
        name="phieu_mo_lai",
    ),
    path("phieu/<int:phieu_id>/xoa/", phieu_xoa, name="phieu_xoa"),
]
