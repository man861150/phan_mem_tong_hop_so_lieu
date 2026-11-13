"""Departments, indicators, annual plans, lookup tables, and form templates."""

import calendar
from datetime import date

from django.core.exceptions import ValidationError
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from simple_history.models import HistoricalRecords

RATIO_THIEU = "Chỉ tiêu tỷ lệ phải có đủ tử số và mẫu số."
RATIO_THUA = "Chỉ chỉ tiêu tỷ lệ mới được gắn tử số và mẫu số."
CUNG_PHONG_CHA = "Chỉ tiêu cha và chỉ tiêu con phải cùng phòng ban."
CUNG_PHONG_LOAI = "Chỉ tiêu và loại hoạt động phải cùng phòng ban."
CUNG_PHONG_LIEN_KET = "Chỉ tiêu liên kết phải cùng phòng ban."
LY_DO_XAC_NHAN = "Điều chỉnh số kế hoạch đã xác nhận phải có lý do."


class ValidatingModel(models.Model):
    """Run clean() on save so admin, seed, and shell share one rule set."""

    class Meta:
        abstract = True

    def save(self, *args, **kwargs):
        if not kwargs.get("update_fields"):
            self.full_clean()
        return super().save(*args, **kwargs)


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


class NhomChiTieu(ValidatingModel):
    phong = models.ForeignKey(
        PhongBan,
        verbose_name="Phòng ban",
        on_delete=models.PROTECT,
        related_name="nhom_chi_tieu",
    )
    ten_mang = models.CharField("Tên mảng", max_length=255)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=1)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Nhóm chỉ tiêu"
        verbose_name_plural = "Nhóm chỉ tiêu"
        ordering = ["phong", "thu_tu", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["phong", "ten_mang"],
                name="catalog_nhomchitieu_phong_ten_uniq",
            )
        ]

    def __str__(self):
        return self.ten_mang


class KieuGhiNhan(models.TextChoices):
    ACTIVITY = "activity", "Theo hoạt động"
    MONTH = "month", "Theo tháng"
    PROJECT = "project", "Theo dự án"


class CachTongHop(models.TextChoices):
    SUM = "sum", "Tổng"
    COUNT = "count", "Đếm"
    CUMULATIVE = "cumulative", "Lũy kế"
    RATIO = "ratio", "Tỷ lệ"
    AVERAGE = "average", "Trung bình"
    LATEST = "latest", "Mới nhất"


class CountSubject(models.TextChoices):
    ACTIVITY = "activity", "Hoạt động"
    PROJECT = "project", "Dự án"


class LoaiHoTro(models.TextChoices):
    NGAY_CONG = "ngay_cong", "Ngày công lao động"
    CHUYEN_GIA = "chuyen_gia", "Chuyên gia"
    DICH_VU = "dich_vu", "Dịch vụ ươm tạo"
    KHAC = "khac", "Khác"


class ChiTieu(ValidatingModel):
    ma_chi_tieu = models.CharField("Mã chỉ tiêu", max_length=40, unique=True)
    ten_chi_tieu = models.CharField("Tên chỉ tiêu", max_length=255)
    don_vi_tinh = models.CharField("Đơn vị tính", max_length=50)
    nhom = models.ForeignKey(
        NhomChiTieu,
        verbose_name="Nhóm chỉ tiêu",
        on_delete=models.PROTECT,
        related_name="chi_tieu",
    )
    chi_tieu_cha = models.ForeignKey(
        "self",
        verbose_name="Chỉ tiêu cha",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="chi_tieu_con",
    )
    kieu_ghi_nhan = models.CharField(
        "Kiểu ghi nhận",
        max_length=16,
        choices=KieuGhiNhan.choices,
    )
    cach_tong_hop = models.CharField(
        "Cách tổng hợp",
        max_length=16,
        choices=CachTongHop.choices,
    )
    chi_tieu_tu_so = models.ForeignKey(
        "self",
        verbose_name="Chỉ tiêu tử số",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ty_le_tu_so",
    )
    chi_tieu_mau_so = models.ForeignKey(
        "self",
        verbose_name="Chỉ tiêu mẫu số",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="ty_le_mau_so",
    )
    phan_loai_doi_tuong = models.BooleanField("Phân loại đối tượng", default=False)
    phan_loai_linh_vuc = models.BooleanField("Phân loại lĩnh vực", default=False)
    gia_tri_toi_thieu = models.DecimalField(
        "Giá trị tối thiểu",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    gia_tri_toi_da = models.DecimalField(
        "Giá trị tối đa",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    khong_vuot_chi_tieu = models.ForeignKey(
        "self",
        verbose_name="Không vượt chỉ tiêu",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="chi_tieu_gioi_han",
    )
    count_subject = models.CharField(
        "Đối tượng đếm",
        max_length=16,
        choices=CountSubject.choices,
        blank=True,
        default="",
    )
    loai_ho_tro = models.CharField(
        "Loại hỗ trợ",
        max_length=16,
        choices=LoaiHoTro.choices,
        blank=True,
        default="",
    )
    loai_hoat_dong = models.ForeignKey(
        "LoaiHoatDong",
        verbose_name="Loại hoạt động",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="chi_tieu_dem",
    )
    dang_su_dung = models.BooleanField("Đang sử dụng", default=True)
    nguon_cho_phep = models.ManyToManyField(
        "NguonSoLieu",
        verbose_name="Nguồn cho phép",
        blank=True,
        related_name="chi_tieu",
    )
    doi_tuong_ap_dung = models.ManyToManyField(
        "DanhMucDoiTuong",
        verbose_name="Đối tượng áp dụng",
        blank=True,
        related_name="chi_tieu",
    )
    history = HistoricalRecords(m2m_fields=["nguon_cho_phep", "doi_tuong_ap_dung"])

    class Meta:
        verbose_name = "Chỉ tiêu"
        verbose_name_plural = "Chỉ tiêu"
        ordering = ["ma_chi_tieu"]

    def __str__(self):
        return f"{self.ma_chi_tieu} — {self.ten_chi_tieu}"

    def _cung_phong(self, other):
        if other is None or not self.nhom_id or not other.nhom_id:
            return True
        return other.nhom.phong_id == self.nhom.phong_id

    def clean(self):
        super().clean()
        errors = {}
        ratio = self.cach_tong_hop == CachTongHop.RATIO
        has_num = self.chi_tieu_tu_so_id is not None
        has_den = self.chi_tieu_mau_so_id is not None
        if ratio and not (has_num and has_den):
            if not has_num:
                errors["chi_tieu_tu_so"] = RATIO_THIEU
            if not has_den:
                errors["chi_tieu_mau_so"] = RATIO_THIEU
        elif not ratio and (has_num or has_den):
            if has_num:
                errors["chi_tieu_tu_so"] = RATIO_THUA
            if has_den:
                errors["chi_tieu_mau_so"] = RATIO_THUA
        if self.pk and self.chi_tieu_tu_so_id == self.pk:
            errors["chi_tieu_tu_so"] = "Tử số không được là chính chỉ tiêu này."
        if self.pk and self.chi_tieu_mau_so_id == self.pk:
            errors["chi_tieu_mau_so"] = "Mẫu số không được là chính chỉ tiêu này."
        if has_num and not self._cung_phong(self.chi_tieu_tu_so):
            errors["chi_tieu_tu_so"] = CUNG_PHONG_LIEN_KET
        if has_den and not self._cung_phong(self.chi_tieu_mau_so):
            errors["chi_tieu_mau_so"] = CUNG_PHONG_LIEN_KET
        if self.chi_tieu_cha_id:
            if self.pk and self.chi_tieu_cha_id == self.pk:
                errors["chi_tieu_cha"] = "Chỉ tiêu cha không được là chính chỉ tiêu này."
            elif not self._cung_phong(self.chi_tieu_cha):
                errors["chi_tieu_cha"] = CUNG_PHONG_CHA
        if self.khong_vuot_chi_tieu_id:
            if self.pk and self.khong_vuot_chi_tieu_id == self.pk:
                errors["khong_vuot_chi_tieu"] = (
                    "Chỉ tiêu giới hạn không được là chính chỉ tiêu này."
                )
            elif not self._cung_phong(self.khong_vuot_chi_tieu):
                errors["khong_vuot_chi_tieu"] = CUNG_PHONG_LIEN_KET
        is_count = self.cach_tong_hop == CachTongHop.COUNT
        if is_count and not self.count_subject:
            errors["count_subject"] = "Chỉ tiêu đếm phải chọn đối tượng đếm."
        if not is_count and self.count_subject:
            errors["count_subject"] = "Chỉ chỉ tiêu đếm mới được chọn đối tượng đếm."
        if self.count_subject == CountSubject.PROJECT and not self.loai_ho_tro:
            errors["loai_ho_tro"] = "Chỉ tiêu đếm dự án phải chọn loại hỗ trợ."
        if self.count_subject != CountSubject.PROJECT and self.loai_ho_tro:
            errors["loai_ho_tro"] = "Chỉ chỉ tiêu đếm dự án mới được gắn loại hỗ trợ."
        if (
            self.gia_tri_toi_thieu is not None
            and self.gia_tri_toi_da is not None
            and self.gia_tri_toi_thieu > self.gia_tri_toi_da
        ):
            errors["gia_tri_toi_da"] = (
                "Giá trị tối đa phải lớn hơn hoặc bằng giá trị tối thiểu."
            )
        self._clean_loai_hoat_dong(errors)
        if errors:
            raise ValidationError(errors)

    def _clean_loai_hoat_dong(self, errors):
        linked = self.loai_hoat_dong_id is not None
        if self.count_subject == CountSubject.ACTIVITY and not linked:
            errors["loai_hoat_dong"] = "Chỉ tiêu đếm hoạt động phải chọn loại hoạt động."
        if self.count_subject != CountSubject.ACTIVITY and linked:
            errors["loai_hoat_dong"] = (
                "Chỉ chỉ tiêu đếm hoạt động mới được gắn loại hoạt động."
            )
        if (
            linked
            and self.nhom_id
            and self.loai_hoat_dong.phong_id != self.nhom.phong_id
        ):
            errors["loai_hoat_dong"] = CUNG_PHONG_LOAI


class HeThongLinhVuc(models.TextChoices):
    QD36 = "qd36", "QĐ 36"
    TT24 = "tt24", "TT 24"


class DanhMucDoiTuong(ValidatingModel):
    ten_doi_tuong = models.CharField("Tên đối tượng", max_length=255, unique=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Đối tượng"
        verbose_name_plural = "Đối tượng"
        ordering = ["ten_doi_tuong"]

    def __str__(self):
        return self.ten_doi_tuong


class DanhMucLinhVuc(ValidatingModel):
    he_thong = models.CharField(
        "Hệ thống",
        max_length=8,
        choices=HeThongLinhVuc.choices,
    )
    ma = models.CharField("Mã", max_length=40)
    ten = models.CharField("Tên", max_length=255)
    cap = models.PositiveIntegerField("Cấp")
    cha = models.ForeignKey(
        "self",
        verbose_name="Lĩnh vực cha",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="linh_vuc_con",
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Lĩnh vực"
        verbose_name_plural = "Lĩnh vực"
        ordering = ["he_thong", "ma"]
        constraints = [
            models.UniqueConstraint(
                fields=["he_thong", "ma"],
                name="catalog_danhmuc_linh_vuc_he_thong_ma_uniq",
            )
        ]

    def __str__(self):
        return f"{self.he_thong}:{self.ma} — {self.ten}"

    def clean(self):
        super().clean()
        if self.cha_id is None:
            return
        if self.pk and self.cha_id == self.pk:
            raise ValidationError({"cha": "Lĩnh vực cha không được là chính mã này."})
        if self.cha.he_thong != self.he_thong:
            raise ValidationError({"cha": "Lĩnh vực cha phải cùng hệ thống."})


class NguonSoLieu(ValidatingModel):
    ten_nguon = models.CharField("Tên nguồn", max_length=255, unique=True)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Nguồn số liệu"
        verbose_name_plural = "Nguồn số liệu"
        ordering = ["ten_nguon"]

    def __str__(self):
        return self.ten_nguon


class LoaiHoatDong(ValidatingModel):
    phong = models.ForeignKey(
        PhongBan,
        verbose_name="Phòng ban",
        on_delete=models.PROTECT,
        related_name="loai_hoat_dong",
    )
    ten_loai = models.CharField("Tên loại", max_length=255)
    co_ke_hoach_so_luong = models.BooleanField("Có kế hoạch số lượng", default=False)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Loại hoạt động"
        verbose_name_plural = "Loại hoạt động"
        ordering = ["phong", "ten_loai"]
        constraints = [
            models.UniqueConstraint(
                fields=["phong", "ten_loai"],
                name="catalog_loaihoatdong_phong_ten_uniq",
            )
        ]

    def __str__(self):
        return self.ten_loai


class BieuMauChiTieu(ValidatingModel):
    loai_hoat_dong = models.ForeignKey(
        LoaiHoatDong,
        verbose_name="Loại hoạt động",
        on_delete=models.CASCADE,
        related_name="bieu_mau",
    )
    chi_tieu = models.ForeignKey(
        ChiTieu,
        verbose_name="Chỉ tiêu",
        on_delete=models.PROTECT,
        related_name="bieu_mau",
    )
    bat_buoc = models.BooleanField("Bắt buộc", default=False)
    thu_tu = models.PositiveIntegerField("Thứ tự", default=1)
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Biểu mẫu chỉ tiêu"
        verbose_name_plural = "Biểu mẫu chỉ tiêu"
        ordering = ["thu_tu", "id"]
        constraints = [
            models.UniqueConstraint(
                fields=["loai_hoat_dong", "chi_tieu"],
                name="catalog_bieumauchitieu_loai_chi_tieu_uniq",
            )
        ]

    def __str__(self):
        return f"{self.loai_hoat_dong} — {self.chi_tieu}"

    def clean(self):
        super().clean()
        if not self.loai_hoat_dong_id or not self.chi_tieu_id:
            return
        if self.chi_tieu.nhom.phong_id != self.loai_hoat_dong.phong_id:
            raise ValidationError({"chi_tieu": CUNG_PHONG_LOAI})


class TrangThaiKeHoach(models.TextChoices):
    DU_THAO = "du_thao", "Dự thảo"
    DA_XAC_NHAN = "da_xac_nhan", "Đã xác nhận"


class ChiTieuKeHoach(ValidatingModel):
    chi_tieu = models.ForeignKey(
        ChiTieu,
        verbose_name="Chỉ tiêu",
        on_delete=models.PROTECT,
        related_name="ke_hoach",
    )
    nam = models.PositiveIntegerField("Năm")
    gia_tri_ke_hoach = models.DecimalField(
        "Giá trị kế hoạch",
        max_digits=18,
        decimal_places=4,
        null=True,
        blank=True,
    )
    doi_tuong = models.ForeignKey(
        DanhMucDoiTuong,
        verbose_name="Đối tượng",
        null=True,
        blank=True,
        on_delete=models.PROTECT,
        related_name="chi_tieu_ke_hoach",
    )
    trang_thai = models.CharField(
        "Trạng thái",
        max_length=16,
        choices=TrangThaiKeHoach.choices,
        default=TrangThaiKeHoach.DU_THAO,
    )
    ly_do = models.TextField("Lý do", blank=True, default="")
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Chỉ tiêu kế hoạch"
        verbose_name_plural = "Chỉ tiêu kế hoạch"
        ordering = ["-nam", "chi_tieu"]
        constraints = [
            models.UniqueConstraint(
                fields=["chi_tieu", "nam", "doi_tuong"],
                nulls_distinct=False,
                name="catalog_chitieukehoach_chi_tieu_nam_doi_tuong_uniq",
            )
        ]

    def __str__(self):
        return f"{self.chi_tieu} — {self.nam}"

    def clean(self):
        super().clean()
        if not self.pk:
            return
        old = ChiTieuKeHoach.objects.get(pk=self.pk)
        if (
            old.trang_thai == TrangThaiKeHoach.DA_XAC_NHAN
            and old.gia_tri_ke_hoach != self.gia_tri_ke_hoach
        ):
            new_reason = (self.ly_do or "").strip()
            old_reason = (old.ly_do or "").strip()
            if not new_reason or new_reason == old_reason:
                raise ValidationError({"ly_do": LY_DO_XAC_NHAN})


class LoaiKy(models.TextChoices):
    THANG = "thang", "Tháng"


class TrangThaiKy(models.TextChoices):
    MO = "mo", "Mở"
    KHOA = "khoa", "Khóa"


class KyBaoCao(ValidatingModel):
    loai_ky = models.CharField(
        "Loại kỳ",
        max_length=16,
        choices=LoaiKy.choices,
        default=LoaiKy.THANG,
    )
    nam = models.PositiveIntegerField("Năm")
    so_ky = models.PositiveSmallIntegerField(
        "Số kỳ",
        validators=[
            MinValueValidator(1, "Số kỳ tháng phải từ 1 đến 12."),
            MaxValueValidator(12, "Số kỳ tháng phải từ 1 đến 12."),
        ],
    )
    tu_ngay = models.DateField("Từ ngày", null=True, blank=True)
    den_ngay = models.DateField("Đến ngày", null=True, blank=True)
    trang_thai = models.CharField(
        "Trạng thái",
        max_length=16,
        choices=TrangThaiKy.choices,
        default=TrangThaiKy.KHOA,
    )
    history = HistoricalRecords()

    class Meta:
        verbose_name = "Kỳ báo cáo"
        verbose_name_plural = "Kỳ báo cáo"
        ordering = ["-nam", "-so_ky"]
        constraints = [
            models.UniqueConstraint(
                fields=["nam", "so_ky"],
                name="catalog_kybaocao_nam_so_ky_uniq",
            )
        ]

    def __str__(self):
        return f"Tháng {self.so_ky}/{self.nam}"

    def clean(self):
        super().clean()
        self.loai_ky = LoaiKy.THANG
        if self.nam is None or self.so_ky is None or not 1 <= self.so_ky <= 12:
            return
        if not self.tu_ngay:
            self.tu_ngay = date(self.nam, self.so_ky, 1)
        if not self.den_ngay:
            last_day = calendar.monthrange(self.nam, self.so_ky)[1]
            self.den_ngay = date(self.nam, self.so_ky, last_day)
        if self.tu_ngay > self.den_ngay:
            raise ValidationError({"den_ngay": "Đến ngày phải không trước từ ngày."})
