"""URL routes for accounts."""

from django.urls import path

from apps.accounts.views import (
    AccountSettingsView,
    LoginView,
    LogoutView,
    profile,
)

app_name = "accounts"

urlpatterns = [
    path("dang-nhap/", LoginView.as_view(), name="login"),
    path("dang-xuat/", LogoutView.as_view(), name="logout"),
    path("ho-so/", profile, name="profile"),
    path("cai-dat/", AccountSettingsView.as_view(), name="settings"),
]
