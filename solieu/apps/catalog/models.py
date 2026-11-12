"""Departments, indicators, annual plans, lookup tables, and form templates."""

from django.db import models
from simple_history.models import HistoricalRecords


class PhongBan(models.Model):
    ma_phong = models.CharField("Mã phòng", max_length=20, unique=True)
    ten_phong = models.CharField("Tên phòng", max_length=255)
    dang_su_dung = models.BooleanField("Đang sử dụng", default=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Phòng ban"
        verbose_name_plural = "Phòng ban"
        ordering = ["ma_phong"]

    def __str__(self):
        return f"{self.ma_phong} — {self.ten_phong}"
