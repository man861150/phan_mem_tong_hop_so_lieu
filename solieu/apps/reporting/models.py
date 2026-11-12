"""Aggregation, Excel export, Word export, and published reports."""

from __future__ import annotations

from django.conf import settings
from django.db import models
from django.utils import timezone


class DinhDangXuat(models.TextChoices):
    XLSX = "xlsx", "Excel"
    DOCX = "docx", "Word"


def _upload_to(instance, filename):
    """Keep generated reports under a dated media folder."""
    return f"bao-cao/{timezone.localtime():%Y/%m}/{filename}"


class BaoCaoDaXuat(models.Model):
    """An immutable report file produced by one export action."""

    ky = models.CharField("Kỳ báo cáo", max_length=100)
    phong = models.ForeignKey(
        "catalog.PhongBan",
        verbose_name="Phòng ban",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bao_cao_da_xuat",
        help_text="Để trống khi báo cáo có phạm vi toàn trung tâm.",
    )
    nguoi_lap = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người lập",
        on_delete=models.PROTECT,
        related_name="bao_cao_da_xuat",
    )
    ngay_lap = models.DateTimeField("Ngày lập", auto_now_add=True)
    dinh_dang = models.CharField(
        "Định dạng",
        max_length=8,
        choices=DinhDangXuat.choices,
    )
    file = models.FileField(
        "Tệp",
        upload_to=_upload_to,
        max_length=255,
    )

    class Meta:
        verbose_name = "Báo cáo đã xuất"
        verbose_name_plural = "Báo cáo đã xuất"
        ordering = ["-ngay_lap", "-id"]

    def __str__(self):
        scope = self.phong.ma_phong if self.phong_id else "Toàn trung tâm"
        return f"{self.ky} — {scope} — {self.get_dinh_dang_display()}"


class BaoCaoDaXuatDong(models.Model):
    """One rollup line frozen at export time."""

    bao_cao = models.ForeignKey(
        BaoCaoDaXuat,
        verbose_name="Báo cáo đã xuất",
        on_delete=models.CASCADE,
        related_name="dong",
    )
    chi_tieu = models.ForeignKey(
        "catalog.ChiTieu",
        verbose_name="Chỉ tiêu",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bao_cao_da_xuat_dong",
    )
    ten_chi_tieu = models.CharField("Tên chỉ tiêu", max_length=255)
    phong = models.ForeignKey(
        "catalog.PhongBan",
        verbose_name="Phòng ban",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="bao_cao_da_xuat_dong",
    )
    period_value = models.DecimalField(
        "Thực hiện trong kỳ",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    cumulative = models.DecimalField(
        "Lũy kế",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    plan = models.DecimalField(
        "Kế hoạch năm",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    percent = models.DecimalField(
        "% hoàn thành",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    note = models.TextField("Ghi chú", blank=True, default="")
    danh_gia = models.TextField("Đánh giá hiệu quả", blank=True, default="")
    breakdown_label = models.TextField(
        "Nhãn phân tích",
        blank=True,
        default="",
        help_text="Tóm tắt các phân tích đối tượng, lĩnh vực, nguồn của dòng.",
    )

    class Meta:
        verbose_name = "Dòng báo cáo đã xuất"
        verbose_name_plural = "Dòng báo cáo đã xuất"
        ordering = ["id"]

    def __str__(self):
        return f"{self.bao_cao_id} — {self.ten_chi_tieu}"
