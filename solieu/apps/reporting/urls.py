"""URL routes for reporting."""

from django.urls import path

from apps.reporting.views import bao_cao, nhap_xlsx, xuat_bao_cao

app_name = "reporting"

urlpatterns = [
    path("bao-cao/", bao_cao, name="bao_cao"),
    path(
        "bao-cao/xuat/<str:dinh_dang>/",
        xuat_bao_cao,
        name="xuat_bao_cao",
    ),
    path("bao-cao/nhap-xlsx/", nhap_xlsx, name="nhap_xlsx"),
]
