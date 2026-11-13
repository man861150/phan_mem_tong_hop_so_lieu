"""Data-entry forms, indicator rows, project support, and approvals."""

from django.conf import settings
from django.core.exceptions import ObjectDoesNotExist, ValidationError
from django.db import models
from simple_history.models import HistoricalRecords

from apps.catalog.models import LoaiHoTro, ValidatingModel


class LoaiPhieu(models.TextChoices):
    HOAT_DONG = "hoat_dong", "Hoạt động"
    THANG = "thang", "Tháng"
    DU_AN = "du_an", "Dự án"


class TrangThaiPhieu(models.TextChoices):
    NHAP = "nhap", "Nháp"
    CHO_DUYET = "cho_duyet", "Chờ duyệt"
    DA_DUYET = "da_duyet", "Đã duyệt"
    TRA_LAI = "tra_lai", "Trả lại"


class HanhDongXuLy(models.TextChoices):
    GUI = "gui", "Gửi duyệt"
    DUYET = "duyet", "Duyệt"
    TRA_LAI = "tra_lai", "Trả lại"
    MO_LAI = "mo_lai", "Mở lại"


class PhieuNhapLieu(ValidatingModel):
    """A unit of approval for an activity, a month, or a project.

    Department rule: an activity phiếu belongs to
    ``hoat_dong.loai_hoat_dong.phong``; a project phiếu belongs to
    ``du_an.phong``; a monthly phiếu carries its department on the phiếu
    itself because the month is entered by one department. Entry views copy
    the target department when they create a phiếu; ``clean()`` only verifies
    the invariant.
    """

    phong = models.ForeignKey(
        "catalog.PhongBan",
        verbose_name="Phòng ban",
        on_delete=models.PROTECT,
        related_name="phieu_nhap_lieu",
    )
    loai_phieu = models.CharField(
        "Loại phiếu",
        max_length=16,
        choices=LoaiPhieu.choices,
    )
    hoat_dong = models.ForeignKey(
        "activities.HoatDong",
        verbose_name="Hoạt động",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="phieu_nhap_lieu",
    )
    ky = models.ForeignKey(
        "catalog.KyBaoCao",
        verbose_name="Kỳ báo cáo",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="phieu_nhap_lieu",
    )
    du_an = models.ForeignKey(
        "activities.DuAn",
        verbose_name="Dự án",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="phieu_nhap_lieu",
    )
    la_phieu_bo_sung = models.BooleanField("Là phiếu bổ sung", default=False)
    trang_thai = models.CharField(
        "Trạng thái",
        max_length=16,
        choices=TrangThaiPhieu.choices,
        default=TrangThaiPhieu.NHAP,
    )
    nguoi_nhap = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người nhập",
        on_delete=models.PROTECT,
        related_name="phieu_nhap_lieu",
    )
    ngay_gui = models.DateTimeField("Ngày gửi", null=True, blank=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Phiếu nhập liệu"
        verbose_name_plural = "Phiếu nhập liệu"
        ordering = ["-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(
                        loai_phieu=LoaiPhieu.HOAT_DONG,
                        hoat_dong__isnull=False,
                        ky__isnull=True,
                        du_an__isnull=True,
                    )
                    | models.Q(
                        loai_phieu=LoaiPhieu.THANG,
                        hoat_dong__isnull=True,
                        ky__isnull=False,
                        du_an__isnull=True,
                    )
                    | models.Q(
                        loai_phieu=LoaiPhieu.DU_AN,
                        hoat_dong__isnull=True,
                        ky__isnull=True,
                        du_an__isnull=False,
                    )
                ),
                name="entry_phieu_target_type_ck",
                violation_error_message=(
                    "Phiếu phải có đúng một đối tượng: hoạt động, kỳ báo cáo "
                    "hoặc dự án, và loại phiếu phải khớp với đối tượng đó."
                ),
            ),
            models.UniqueConstraint(
                fields=["hoat_dong"],
                condition=models.Q(
                    loai_phieu=LoaiPhieu.HOAT_DONG,
                    la_phieu_bo_sung=False,
                ),
                name="entry_phieu_activity_primary_uniq",
                violation_error_message=(
                    "Mỗi hoạt động chỉ có một phiếu chính."
                ),
            ),
            models.UniqueConstraint(
                fields=["phong", "ky"],
                condition=models.Q(
                    loai_phieu=LoaiPhieu.THANG,
                    la_phieu_bo_sung=False,
                ),
                name="entry_phieu_month_primary_uniq",
                violation_error_message=(
                    "Mỗi phòng chỉ có một phiếu chính cho một kỳ."
                ),
            ),
            models.UniqueConstraint(
                fields=["du_an"],
                condition=models.Q(
                    loai_phieu=LoaiPhieu.DU_AN,
                    la_phieu_bo_sung=False,
                ),
                name="entry_phieu_project_primary_uniq",
                violation_error_message=(
                    "Mỗi dự án chỉ có một phiếu chính."
                ),
            ),
        ]

    def __str__(self):
        target = self.hoat_dong or self.ky or self.du_an
        if target is None:
            return self.get_loai_phieu_display()
        return f"{self.get_loai_phieu_display()} — {target}"

    def clean(self):
        super().clean()
        targets = [
            name
            for name in ("hoat_dong", "ky", "du_an")
            if getattr(self, f"{name}_id") is not None
        ]
        if len(targets) != 1:
            return
        target = targets[0]
        expected_type = {
            "hoat_dong": LoaiPhieu.HOAT_DONG,
            "ky": LoaiPhieu.THANG,
            "du_an": LoaiPhieu.DU_AN,
        }[target]
        if self.loai_phieu != expected_type:
            return
        expected_phong_id = self._target_phong_id(target)
        if expected_phong_id is not None and self.phong_id != expected_phong_id:
            raise ValidationError(
                {
                    "phong": (
                        "Phòng ban của phiếu phải trùng với phòng ban của "
                        "đối tượng."
                    )
                }
            )

    def _target_phong_id(self, target):
        try:
            obj = getattr(self, target)
        except ObjectDoesNotExist:
            return None
        if target == "hoat_dong":
            try:
                return obj.loai_hoat_dong.phong_id
            except ObjectDoesNotExist:
                return None
        if target == "du_an":
            return obj.phong_id
        return None


class LichSuXuLy(ValidatingModel):
    """One workflow transition for a phiếu, including its comment."""

    phieu = models.ForeignKey(
        PhieuNhapLieu,
        verbose_name="Phiếu nhập liệu",
        on_delete=models.CASCADE,
        related_name="lich_su_xu_ly",
    )
    nguoi_xu_ly = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        verbose_name="Người xử lý",
        on_delete=models.PROTECT,
        related_name="lich_su_xu_ly",
    )
    hanh_dong = models.CharField(
        "Hành động",
        max_length=16,
        choices=HanhDongXuLy.choices,
    )
    y_kien = models.TextField("Ý kiến", blank=True, default="")
    thoi_diem = models.DateTimeField("Thời điểm", auto_now_add=True)

    class Meta:
        verbose_name = "Lịch sử xử lý"
        verbose_name_plural = "Lịch sử xử lý"
        ordering = ["thoi_diem", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    ~models.Q(
                        hanh_dong__in=(
                            HanhDongXuLy.TRA_LAI,
                            HanhDongXuLy.MO_LAI,
                        )
                    )
                    | ~models.Q(y_kien="")
                ),
                name="entry_lichsuxuly_comment_required_ck",
                violation_error_message=(
                    "Trả lại hoặc mở lại phiếu phải có ý kiến."
                ),
            )
        ]

    def __str__(self):
        return f"{self.phieu} — {self.get_hanh_dong_display()}"

    def clean(self):
        super().clean()
        self.y_kien = (self.y_kien or "").strip()
        if (
            self.hanh_dong
            in (HanhDongXuLy.TRA_LAI, HanhDongXuLy.MO_LAI)
            and not self.y_kien
        ):
            raise ValidationError(
                {
                    "y_kien": (
                        "Vui lòng nhập ý kiến khi trả lại hoặc mở lại phiếu."
                    )
                }
            )


class SoLieu(ValidatingModel):
    """One entered number: indicator, value, and an optional split.

    Every indicator is a row. Splits use at most one classification, either
    ``doi_tuong`` or ``linh_vuc``; a total row uses neither.
    """

    phieu = models.ForeignKey(
        PhieuNhapLieu,
        verbose_name="Phiếu nhập liệu",
        on_delete=models.CASCADE,
        related_name="so_lieu",
    )
    chi_tieu = models.ForeignKey(
        "catalog.ChiTieu",
        verbose_name="Chỉ tiêu",
        on_delete=models.PROTECT,
        related_name="so_lieu",
    )
    gia_tri = models.DecimalField(
        "Giá trị",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    doi_tuong = models.ForeignKey(
        "catalog.DanhMucDoiTuong",
        verbose_name="Đối tượng",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="so_lieu",
    )
    linh_vuc = models.ForeignKey(
        "catalog.DanhMucLinhVuc",
        verbose_name="Lĩnh vực",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="so_lieu",
    )
    nguon = models.ForeignKey(
        "catalog.NguonSoLieu",
        verbose_name="Nguồn số liệu",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="so_lieu",
    )
    ghi_chu = models.TextField("Ghi chú", blank=True, default="")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Số liệu"
        verbose_name_plural = "Số liệu"
        ordering = ["phieu", "chi_tieu", "id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(doi_tuong__isnull=True)
                    | models.Q(linh_vuc__isnull=True)
                ),
                name="entry_solieu_one_split_ck",
                violation_error_message=(
                    "Dòng số liệu chỉ được phân loại theo đối tượng hoặc "
                    "lĩnh vực, không được cả hai."
                ),
            )
        ]

    def __str__(self):
        return f"{self.phieu} — {self.chi_tieu}"


class HoTroDuAn(ValidatingModel):
    """A dated support line on a project phiếu."""

    du_an = models.ForeignKey(
        "activities.DuAn",
        verbose_name="Dự án",
        on_delete=models.PROTECT,
        related_name="ho_tro_du_an",
    )
    phieu = models.ForeignKey(
        PhieuNhapLieu,
        verbose_name="Phiếu nhập liệu",
        on_delete=models.CASCADE,
        related_name="ho_tro_du_an",
    )
    loai_ho_tro = models.CharField(
        "Loại hỗ trợ",
        max_length=16,
        choices=LoaiHoTro.choices,
    )
    noi_dung = models.TextField("Nội dung")
    so_chuyen_gia = models.DecimalField(
        "Số chuyên gia",
        max_digits=12,
        decimal_places=2,
        null=True,
        blank=True,
    )
    ngay_ho_tro = models.DateField("Ngày hỗ trợ")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Hỗ trợ dự án"
        verbose_name_plural = "Hỗ trợ dự án"
        ordering = ["-ngay_ho_tro", "-id"]
        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(so_chuyen_gia__isnull=True)
                    | models.Q(so_chuyen_gia__gte=0)
                ),
                name="entry_hotro_expert_nonneg_ck",
                violation_error_message="Số chuyên gia không được âm.",
            )
        ]

    def __str__(self):
        return (
            f"{self.du_an} — {self.get_loai_ho_tro_display()} "
            f"({self.ngay_ho_tro})"
        )

    def clean(self):
        super().clean()
        if self.phieu_id is None:
            return
        try:
            phieu = self.phieu
        except ObjectDoesNotExist:
            return
        if phieu.loai_phieu != LoaiPhieu.DU_AN:
            raise ValidationError(
                {"phieu": "Dòng hỗ trợ phải thuộc phiếu dự án."}
            )
        if phieu.du_an_id != self.du_an_id:
            raise ValidationError(
                {
                    "phieu": (
                        "Phiếu phải trỏ tới cùng dự án với dòng hỗ trợ."
                    )
                }
            )
