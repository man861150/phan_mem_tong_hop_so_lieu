"""Activity types, activities, partner units, and projects."""

from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import ValidatingModel


class DonViPhoiHop(ValidatingModel):
    ten_don_vi = models.CharField("Tên đơn vị", max_length=255)
    doi_tuong = models.ForeignKey(
        "catalog.DanhMucDoiTuong",
        verbose_name="Loại đơn vị",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="don_vi_phoi_hop",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Đơn vị phối hợp"
        verbose_name_plural = "Đơn vị phối hợp"
        ordering = ["ten_don_vi", "id"]

    def __str__(self):
        return self.ten_don_vi
