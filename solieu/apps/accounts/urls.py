"""URL routes for accounts."""

from django.urls import path

from apps.accounts.views import LoginView, LogoutView

app_name = "accounts"

urlpatterns = [
    path("dang-nhap/", LoginView.as_view(), name="login"),
    path("dang-xuat/", LogoutView.as_view(), name="logout"),
]
