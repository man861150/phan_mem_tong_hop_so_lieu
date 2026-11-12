"""URL routes for reporting."""

from django.urls import path

from apps.reporting.views import (
    bao_cao,
    da_xuat,
    lich_su,
    nhap_xlsx,
    tai_bao_cao,
    tien_do,
    tien_do_chi_tiet,
    xuat_bao_cao,
)

app_name = "reporting"

urlpatterns = [
    path("tien-do/", tien_do, name="tien_do"),
    path(
        "tien-do/<int:chi_tieu_id>/",
        tien_do_chi_tiet,
        name="tien_do_chi_tiet",
    ),
    path("lich-su/", lich_su, name="lich_su"),
    path("bao-cao/", bao_cao, name="bao_cao"),
    path("bao-cao/da-xuat/", da_xuat, name="da_xuat"),
    path(
        "bao-cao/da-xuat/<int:bao_cao_id>/tai/",
        tai_bao_cao,
        name="tai_bao_cao",
    ),
    path(
        "bao-cao/xuat/<str:dinh_dang>/",
        xuat_bao_cao,
        name="xuat_bao_cao",
    ),
    path("bao-cao/nhap-xlsx/", nhap_xlsx, name="nhap_xlsx"),
]
