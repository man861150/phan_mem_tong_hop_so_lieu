"""Activity types, activities, partner units, and projects."""

from django.core.exceptions import ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import (
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    LoaiHoatDong,
    PhongBan,
    ValidatingModel,
)

AD_HOC_ACTIVITY_TYPE_NAME = "Nhiệm vụ phát sinh"


class HinhThucHoatDong(models.TextChoices):
    TRUC_TIEP = "truc_tiep", "Trực tiếp"
    TRUC_TUYEN = "truc_tuyen", "Trực tuyến"
    KET_HOP = "ket_hop", "Kết hợp"


class TrangThaiHoatDong(models.TextChoices):
    KE_HOACH = "ke_hoach", "Kế hoạch"
    DA_TO_CHUC = "da_to_chuc", "Đã tổ chức"


class ChuongTrinhDuAn(models.TextChoices):
    NQ20 = "nq20", "NQ20"
    NQ64 = "nq64", "NQ64"
    NGOAI_NQ20 = "ngoai_nq20", "Ngoài ngân sách NQ20"


class HinhThucDuAn(models.TextChoices):
    UOM_TAO = "uom_tao", "Ươm tạo"
    TANG_TOC = "tang_toc", "Tăng tốc"


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


class HoatDong(ValidatingModel):
    loai_hoat_dong = models.ForeignKey(
        LoaiHoatDong,
        verbose_name="Loại hoạt động",
        on_delete=models.PROTECT,
        related_name="hoat_dong",
    )
    ten = models.CharField("Tên hoạt động", max_length=255)
    tu_ngay = models.DateField("Từ ngày")
    den_ngay = models.DateField("Đến ngày", blank=True)
    dia_diem = models.CharField("Địa điểm", max_length=255, blank=True)
    hinh_thuc = models.CharField(
        "Hình thức",
        max_length=16,
        choices=HinhThucHoatDong.choices,
        default=HinhThucHoatDong.TRUC_TIEP,
    )
    linh_vuc = models.ForeignKey(
        DanhMucLinhVuc,
        verbose_name="Lĩnh vực",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="hoat_dong",
    )
    doi_tuong_huong_toi = models.ManyToManyField(
        DanhMucDoiTuong,
        verbose_name="Đối tượng hướng tới",
        blank=True,
        related_name="hoat_dong",
    )
    trang_thai = models.CharField(
        "Trạng thái",
        max_length=16,
        choices=TrangThaiHoatDong.choices,
        default=TrangThaiHoatDong.KE_HOACH,
    )
    noi_dung = models.TextField("Nội dung", blank=True)
    ket_qua = models.TextField("Kết quả", blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Hoạt động"
        verbose_name_plural = "Hoạt động"
        ordering = ["-tu_ngay", "-id"]

    def __str__(self):
        return self.ten

    @property
    def phong(self):
        return self.loai_hoat_dong.phong

    @property
    def la_nhiem_vu_phat_sinh(self):
        return self.loai_hoat_dong.ten_loai == AD_HOC_ACTIVITY_TYPE_NAME

    def clean(self):
        super().clean()
        errors = {}
        if self.tu_ngay and not self.den_ngay:
            self.den_ngay = self.tu_ngay
        if self.tu_ngay and self.den_ngay and self.den_ngay < self.tu_ngay:
            errors["den_ngay"] = "Ngày kết thúc không được trước ngày bắt đầu."
        if (
            self.trang_thai == TrangThaiHoatDong.DA_TO_CHUC
            and self.loai_hoat_dong_id
            and self.la_nhiem_vu_phat_sinh
        ):
            if not (self.noi_dung or "").strip():
                errors["noi_dung"] = (
                    "Nhiệm vụ phát sinh phải có nội dung trước khi chuyển sang "
                    "Đã tổ chức."
                )
            if not (self.ket_qua or "").strip():
                errors["ket_qua"] = (
                    "Nhiệm vụ phát sinh phải có kết quả trước khi chuyển sang "
                    "Đã tổ chức."
                )
        if errors:
            raise ValidationError(errors)


class HoatDongDonVi(models.Model):
    hoat_dong = models.ForeignKey(
        HoatDong,
        verbose_name="Hoạt động",
        on_delete=models.CASCADE,
        related_name="don_vi_tham_gia",
    )
    don_vi = models.ForeignKey(
        DonViPhoiHop,
        verbose_name="Đơn vị phối hợp",
        on_delete=models.PROTECT,
        related_name="hoat_dong_tham_gia",
    )
    vai_tro = models.CharField("Vai trò", max_length=255, blank=True)

    class Meta:
        verbose_name = "Đơn vị phối hợp của hoạt động"
        verbose_name_plural = "Đơn vị phối hợp của hoạt động"
        ordering = ["don_vi__ten_don_vi", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["hoat_dong", "don_vi"],
                name="activities_hoatdongdonvi_hoatdong_donvi_uniq",
            )
        ]

    def __str__(self):
        return f"{self.hoat_dong} — {self.don_vi}"


class DuAn(ValidatingModel):
    phong = models.ForeignKey(
        PhongBan,
        verbose_name="Phòng ban",
        on_delete=models.PROTECT,
        related_name="du_an",
    )
    ten_du_an = models.CharField("Tên dự án", max_length=255)
    chuong_trinh = models.CharField(
        "Chương trình",
        max_length=16,
        choices=ChuongTrinhDuAn.choices,
    )
    hinh_thuc = models.CharField(
        "Hình thức",
        max_length=16,
        choices=HinhThucDuAn.choices,
    )
    nam = models.PositiveIntegerField("Năm")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Dự án"
        verbose_name_plural = "Dự án"
        ordering = ["-nam", "ten_du_an", "id"]

    def __str__(self):
        return self.ten_du_an
