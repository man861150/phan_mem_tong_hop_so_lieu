"""Departments, indicators, annual plans, lookup tables, and form templates."""

from django.contrib import admin
from simple_history.admin import SimpleHistoryAdmin

from apps.catalog.models import PhongBan


@admin.register(PhongBan)
class PhongBanAdmin(SimpleHistoryAdmin):
    list_display = ("ma_phong", "ten_phong", "dang_su_dung")
    list_filter = ("dang_su_dung",)
    search_fields = ("ma_phong", "ten_phong")
    ordering = ("ma_phong",)
