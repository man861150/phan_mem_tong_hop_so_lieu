"""Deterministic demo data for the localhost website.

The data in this module is synthetic. Names are marked "(dữ liệu mẫu)" or
"(đơn vị mẫu)" so they cannot be mistaken for a real catalog. The seed command
uses compare-before-save helpers, so a second run creates no duplicate rows and
no extra history rows.
"""

from __future__ import annotations

import calendar
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from django.apps import apps
from django.conf import settings
from django.core.management.base import CommandError
from django.db import connection, transaction

from apps.accounts.models import User
from apps.activities.models import (
    ChuongTrinhDuAn,
    DonViPhoiHop,
    DuAn,
    HinhThucDuAn,
    HinhThucHoatDong,
    HoatDong,
    HoatDongDonVi,
    TrangThaiHoatDong,
)
from apps.catalog.models import (
    BieuMauChiTieu,
    CachTongHop,
    ChiTieu,
    ChiTieuKeHoach,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    KieuGhiNhan,
    KyBaoCao,
    LoaiHoatDong,
    LoaiHoTro,
    NguonSoLieu,
    PhongBan,
    TrangThaiKeHoach,
    TrangThaiKy,
)
from apps.entry import workflow
from apps.entry.models import (
    HanhDongXuLy,
    HoTroDuAn,
    LichSuXuLy,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)
from apps.reporting.docx_export import build_docx
from apps.reporting.exports import create_export_record, export_filename
from apps.reporting.models import BaoCaoDaXuat
from apps.reporting.periods import KIND_MONTH, KIND_YEAR, period_label, resolve_period
from apps.reporting.report_data import (
    build_department_reports,
    collect_gaps,
    rollup_by_department,
)
from apps.reporting.xlsx_export import build_workbook

TZ = ZoneInfo("Asia/Ho_Chi_Minh")
ZERO = Decimal("0")
STEP = Decimal("0.0001")
DEMO_YEAR = 2026
PREVIOUS_YEAR = 2025
DEMO_SUFFIX = " (dữ liệu mẫu)"
RETURN_COMMENT = "Đề nghị bổ sung minh chứng và rà lại số liệu trước khi gửi lại."
REOPEN_COMMENT = "Mở lại để cập nhật số liệu theo biên bản đã ký."


def _d(value: str) -> Decimal:
    return Decimal(value)


def _q(value: Decimal) -> Decimal:
    return Decimal(value).quantize(STEP)


def _at(day: date, hour: int = 9, minute: int = 0) -> datetime:
    return datetime(day.year, day.month, day.day, hour, minute, tzinfo=TZ)


def _month_end(year: int, month: int) -> date:
    return date(year, month, calendar.monthrange(year, month)[1])


# ---------------------------------------------------------------------------
# Dataset definitions
# ---------------------------------------------------------------------------

PARTNER_UNITS = {
    "bach-khoa": (
        "Trường Đại học Bách khoa TP.HCM (đơn vị mẫu)",
        "Viện/trường",
    ),
    "cong-nghe-xanh": (
        "Công ty TNHH Công nghệ Xanh (đơn vị mẫu)",
        "Doanh nghiệp",
    ),
    "so-khcn": (
        "Sở Khoa học và Công nghệ TP.HCM (đơn vị mẫu)",
        "Sở ban ngành",
    ),
    "vien-sinh-hoc": (
        "Viện Công nghệ Sinh học (đơn vị mẫu)",
        "Viện/trường",
    ),
    "nic": (
        "Trung tâm Đổi mới Sáng tạo Quốc gia (đơn vị mẫu)",
        "Sở ban ngành",
    ),
    "chuyen-doi-so": (
        "Công ty CP Chuyển đổi số Việt (đơn vị mẫu)",
        "Doanh nghiệp",
    ),
    "hiep-hoi": (
        "Hiệp hội Doanh nghiệp Công nghệ (đơn vị mẫu)",
        "Doanh nghiệp",
    ),
    "kinh-te": (
        "Trường Đại học Kinh tế TP.HCM (đơn vị mẫu)",
        "Viện/trường",
    ),
}

DOI_TUONG = ("Sở ban ngành", "Viện/trường", "Doanh nghiệp", "Sinh viên/Học viên", "Cá nhân")
HAI = ("Viện/trường", "Doanh nghiệp")
BON = ("Sở ban ngành", "Viện/trường", "Doanh nghiệp", "Sinh viên/Học viên")


@dataclass(frozen=True)
class ActivitySpec:
    key: str
    phong: str
    loai: str
    ten: str
    tu_ngay: date
    den_ngay: date
    dia_diem: str
    hinh_thuc: str
    trang_thai: str
    partners: tuple[str, ...] = ()
    doi_tuong: tuple[str, ...] = ()
    linh_vuc: str | None = None
    noi_dung: str = ""
    ket_qua: str = ""
    phieu_status: str | None = None
    factor: Decimal = field(default_factory=Decimal)
    missing_code: str | None = None
    changed_after_send: bool = False
    reopened: bool = False


def _a(
    key: str,
    phong: str,
    loai: str,
    ten: str,
    tu_ngay: date,
    den_ngay: date | None,
    dia_diem: str,
    hinh_thuc: str,
    trang_thai: str,
    *,
    partners: tuple[str, ...] = (),
    doi_tuong: tuple[str, ...] = (),
    linh_vuc: str | None = None,
    noi_dung: str = "",
    ket_qua: str = "",
    phieu_status: str | None = None,
    factor: str = "1",
    missing_code: str | None = None,
    changed_after_send: bool = False,
    reopened: bool = False,
) -> ActivitySpec:
    return ActivitySpec(
        key=key,
        phong=phong,
        loai=loai,
        ten=ten,
        tu_ngay=tu_ngay,
        den_ngay=den_ngay or tu_ngay,
        dia_diem=dia_diem,
        hinh_thuc=hinh_thuc,
        trang_thai=trang_thai,
        partners=partners,
        doi_tuong=doi_tuong,
        linh_vuc=linh_vuc,
        noi_dung=noi_dung,
        ket_qua=ket_qua,
        phieu_status=phieu_status,
        factor=_d(factor),
        missing_code=missing_code,
        changed_after_send=changed_after_send,
        reopened=reopened,
    )


D = TrangThaiHoatDong.DA_TO_CHUC
K = TrangThaiHoatDong.KE_HOACH
TT = HinhThucHoatDong.TRUC_TIEP
TUYEN = HinhThucHoatDong.TRUC_TUYEN
KET_HOP = HinhThucHoatDong.KET_HOP

ACTIVITY_SPECS = (
    # HTKN 2026 -------------------------------------------------------------
    _a(
        "htkn-lop-1",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 1" + DEMO_SUFFIX,
        date(2026, 3, 12),
        date(2026, 3, 13),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "cong-nghe-xanh"),
        doi_tuong=HAI,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "htkn-lop-2",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 2" + DEMO_SUFFIX,
        date(2026, 4, 16),
        date(2026, 4, 17),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "hiep-hoi"),
        doi_tuong=HAI,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "htkn-lop-3",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 3" + DEMO_SUFFIX,
        date(2026, 6, 11),
        date(2026, 6, 12),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("cong-nghe-xanh", "chuyen-doi-so"),
        doi_tuong=HAI,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.10",
    ),
    _a(
        "htkn-lop-4",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 4" + DEMO_SUFFIX,
        date(2026, 9, 17),
        date(2026, 9, 18),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "nic"),
        doi_tuong=HAI,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.95",
    ),
    _a(
        "htkn-lop-5",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 5" + DEMO_SUFFIX,
        date(2026, 10, 15),
        date(2026, 10, 16),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("hiep-hoi", "chuyen-doi-so"),
        doi_tuong=HAI,
        phieu_status=TrangThaiPhieu.CHO_DUYET,
        factor="1.05",
        changed_after_send=True,
    ),
    _a(
        "htkn-lop-6",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 6" + DEMO_SUFFIX,
        date(2026, 11, 5),
        date(2026, 11, 6),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa",),
        doi_tuong=HAI,
        phieu_status=TrangThaiPhieu.NHAP,
        factor="1.00",
        missing_code="HTKN-LOP-KS",
    ),
    _a(
        "htkn-hn-1",
        "HTKN",
        "Hội nghị/hội thảo",
        "Hội nghị kết nối công nghệ và đầu tư" + DEMO_SUFFIX,
        date(2026, 5, 21),
        date(2026, 5, 21),
        "Trung tâm Hội nghị TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn", "hiep-hoi"),
        doi_tuong=BON,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "htkn-hn-2",
        "HTKN",
        "Hội nghị/hội thảo",
        "Hội thảo chuyển đổi số trong sản xuất" + DEMO_SUFFIX,
        date(2026, 8, 20),
        date(2026, 8, 20),
        "Trực tuyến trên nền tảng họp trực tuyến (địa điểm mẫu)",
        TUYEN,
        D,
        partners=("chuyen-doi-so", "nic"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.10",
    ),
    _a(
        "htkn-hn-gap",
        "HTKN",
        "Hội nghị/hội thảo",
        "Hội nghị chuyên đề tháng 10" + DEMO_SUFFIX,
        date(2026, 10, 8),
        date(2026, 10, 8),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn",),
        doi_tuong=BON,
        phieu_status=None,
    ),
    _a(
        "htkn-tl-1",
        "HTKN",
        "Triển lãm",
        "Triển lãm công nghệ xanh 2026" + DEMO_SUFFIX,
        date(2026, 7, 9),
        date(2026, 7, 11),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("cong-nghe-xanh", "hiep-hoi", "so-khcn"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "htkn-tl-2",
        "HTKN",
        "Triển lãm",
        "Triển lãm thiết bị thông minh" + DEMO_SUFFIX,
        date(2026, 11, 26),
        date(2026, 11, 28),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        TT,
        K,
        partners=("chuyen-doi-so", "nic"),
        doi_tuong=DOI_TUONG,
    ),
    _a(
        "htkn-adhoc-1",
        "HTKN",
        "Nhiệm vụ phát sinh",
        "Nhiệm vụ phát sinh: hỗ trợ đoàn khảo sát" + DEMO_SUFFIX,
        date(2026, 9, 25),
        date(2026, 9, 25),
        "Trụ sở Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn",),
        doi_tuong=("Sở ban ngành",),
        noi_dung=(
            "Tiếp đoàn khảo sát của Sở KH&CN, giới thiệu mô hình ươm tạo "
            "và kết nối ba doanh nghiệp công nghệ."
        ),
        ket_qua=(
            "Đoàn ghi nhận mô hình hỗ trợ; hai doanh nghiệp đề nghị được "
            "tư vấn chuyên sâu trong quý IV."
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    _a(
        "htkn-adhoc-2",
        "HTKN",
        "Nhiệm vụ phát sinh",
        "Nhiệm vụ phát sinh: tư vấn trực tuyến" + DEMO_SUFFIX,
        date(2026, 10, 20),
        date(2026, 10, 20),
        "Trực tuyến trên nền tảng họp trực tuyến (địa điểm mẫu)",
        TUYEN,
        D,
        doi_tuong=("Doanh nghiệp",),
        noi_dung="Tư vấn trực tuyến cho doanh nghiệp về lộ trình chuyển đổi số.",
        ket_qua="Doanh nghiệp đang hoàn thiện hồ sơ để gửi lại.",
        phieu_status=TrangThaiPhieu.NHAP,
    ),
    # GDCN 2026 -------------------------------------------------------------
    _a(
        "gdcn-tm-1",
        "GDCN",
        "Techmart",
        "Techmart Công nghệ sinh học 2026" + DEMO_SUFFIX,
        date(2026, 3, 26),
        date(2026, 3, 28),
        "Trung tâm Hội chợ và Triển lãm TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn", "vien-sinh-hoc", "hiep-hoi"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "gdcn-tm-2",
        "GDCN",
        "Techmart",
        "Techmart Cơ khí chính xác 2026" + DEMO_SUFFIX,
        date(2026, 6, 18),
        date(2026, 6, 20),
        "Trung tâm Hội chợ và Triển lãm TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "cong-nghe-xanh", "hiep-hoi"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.05",
    ),
    _a(
        "gdcn-td-1",
        "GDCN",
        "Trình diễn công nghệ",
        "Trình diễn công nghệ AI và tự động hóa" + DEMO_SUFFIX,
        date(2026, 4, 23),
        date(2026, 4, 23),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("bach-khoa", "chuyen-doi-so", "nic"),
        doi_tuong=HAI,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "gdcn-td-2",
        "GDCN",
        "Trình diễn công nghệ",
        "Trình diễn công nghệ vật liệu mới" + DEMO_SUFFIX,
        date(2026, 5, 28),
        date(2026, 5, 28),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("vien-sinh-hoc", "bach-khoa"),
        doi_tuong=HAI,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.95",
    ),
    _a(
        "gdcn-td-3",
        "GDCN",
        "Trình diễn công nghệ",
        "Trình diễn công nghệ nông nghiệp thông minh" + DEMO_SUFFIX,
        date(2026, 9, 10),
        date(2026, 9, 10),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("cong-nghe-xanh", "hiep-hoi"),
        doi_tuong=HAI,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.10",
    ),
    _a(
        "gdcn-td-4",
        "GDCN",
        "Trình diễn công nghệ",
        "Trình diễn công nghệ năng lượng tái tạo" + DEMO_SUFFIX,
        date(2026, 10, 22),
        date(2026, 10, 22),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("chuyen-doi-so", "nic"),
        doi_tuong=HAI,
        phieu_status=TrangThaiPhieu.CHO_DUYET,
        factor="1.05",
    ),
    _a(
        "gdcn-cafe-1",
        "GDCN",
        "Cafe công nghệ",
        "Cafe công nghệ: kết nối cung – cầu" + DEMO_SUFFIX,
        date(2026, 4, 9),
        date(2026, 4, 9),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("hiep-hoi", "chuyen-doi-so"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "gdcn-cafe-2",
        "GDCN",
        "Cafe công nghệ",
        "Cafe công nghệ: đổi mới sáng tạo mở" + DEMO_SUFFIX,
        date(2026, 8, 6),
        date(2026, 8, 6),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "nic"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.05",
    ),
    _a(
        "gdcn-cafe-3",
        "GDCN",
        "Cafe công nghệ",
        "Cafe công nghệ: kết nối đầu tư" + DEMO_SUFFIX,
        date(2026, 10, 2),
        date(2026, 10, 2),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("hiep-hoi", "kinh-te"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status="mo_lai",
        factor="0.90",
    ),
    _a(
        "gdcn-tinh-1",
        "GDCN",
        "Sự kiện KH&CN tại tỉnh thành – trên toàn quốc",
        "Sự kiện KH&CN tại tỉnh thành – trên toàn quốc 2026" + DEMO_SUFFIX,
        date(2026, 7, 16),
        date(2026, 7, 17),
        "Trung tâm Hội nghị tỉnh (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn", "hiep-hoi"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "gdcn-tinh-2",
        "GDCN",
        "Sự kiện KH&CN tại tỉnh thành – khu vực phía Nam",
        "Sự kiện KH&CN tại tỉnh thành – khu vực phía Nam 2026" + DEMO_SUFFIX,
        date(2026, 9, 24),
        date(2026, 9, 25),
        "Trung tâm Hội nghị khu vực (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn", "vien-sinh-hoc"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.10",
    ),
    _a(
        "gdcn-tl-1",
        "GDCN",
        "Triển lãm Sàn GDCN tham gia",
        "Triển lãm Sàn GDCN tham gia 2026" + DEMO_SUFFIX,
        date(2026, 11, 27),
        date(2026, 11, 29),
        "Trung tâm Hội chợ và Triển lãm TP.HCM (địa điểm mẫu)",
        TT,
        K,
        partners=("hiep-hoi", "cong-nghe-xanh"),
        doi_tuong=DOI_TUONG,
    ),
    _a(
        "gdcn-ht-1",
        "GDCN",
        "Hợp tác công nghệ",
        "Hợp tác công nghệ: kết nối viện trường – doanh nghiệp" + DEMO_SUFFIX,
        date(2026, 10, 29),
        date(2026, 10, 29),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "hiep-hoi"),
        doi_tuong=HAI,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "gdcn-kn-1",
        "GDCN",
        "Kết nối ý tưởng",
        "Kết nối ý tưởng khởi nghiệp 2026" + DEMO_SUFFIX,
        date(2026, 6, 25),
        date(2026, 6, 25),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("nic", "kinh-te"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    # TTTK 2026 -------------------------------------------------------------
    _a(
        "tttk-ht-1",
        "TTTK",
        "Hội thảo xu hướng công nghệ",
        "Hội thảo xu hướng công nghệ: AI tạo sinh" + DEMO_SUFFIX,
        date(2026, 5, 14),
        date(2026, 5, 14),
        "Hội trường Trung tâm Thông tin – Thống kê (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("bach-khoa", "chuyen-doi-so"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.00",
    ),
    _a(
        "tttk-ht-2",
        "TTTK",
        "Hội thảo xu hướng công nghệ",
        "Hội thảo xu hướng công nghệ: bán dẫn" + DEMO_SUFFIX,
        date(2026, 9, 18),
        date(2026, 9, 18),
        "Hội trường Trung tâm Thông tin – Thống kê (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "nic"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-02",
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="1.10",
    ),
    _a(
        "tttk-ht-3",
        "TTTK",
        "Hội thảo xu hướng công nghệ",
        "Hội thảo xu hướng công nghệ: chuyển đổi số y tế" + DEMO_SUFFIX,
        date(2026, 10, 16),
        date(2026, 10, 16),
        "Trực tuyến trên nền tảng họp trực tuyến (địa điểm mẫu)",
        TUYEN,
        D,
        partners=("kinh-te", "chuyen-doi-so"),
        doi_tuong=DOI_TUONG,
        linh_vuc="MAU-01",
        phieu_status=TrangThaiPhieu.TRA_LAI,
        factor="1.00",
        changed_after_send=True,
    ),
    # 2025 examples ---------------------------------------------------------
    _a(
        "htkn-lop-2025",
        "HTKN",
        "Lớp huấn luyện",
        "Lớp huấn luyện kỹ năng số 2025" + DEMO_SUFFIX,
        date(2025, 4, 10),
        date(2025, 4, 11),
        "Hội trường Trung tâm Đổi mới Sáng tạo (địa điểm mẫu)",
        TT,
        D,
        partners=("bach-khoa", "hiep-hoi"),
        doi_tuong=HAI,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "htkn-hn-2025",
        "HTKN",
        "Hội nghị/hội thảo",
        "Hội nghị kết nối công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 8, 14),
        date(2025, 8, 14),
        "Trung tâm Hội nghị TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn",),
        doi_tuong=BON,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.95",
    ),
    _a(
        "htkn-tl-2025",
        "HTKN",
        "Triển lãm",
        "Triển lãm công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 7, 3),
        date(2025, 7, 5),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("hiep-hoi",),
        doi_tuong=DOI_TUONG,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.85",
    ),
    _a(
        "gdcn-tm-2025",
        "GDCN",
        "Techmart",
        "Techmart Công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 5, 15),
        date(2025, 5, 17),
        "Trung tâm Hội chợ và Triển lãm TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("so-khcn", "hiep-hoi"),
        doi_tuong=DOI_TUONG,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "gdcn-td-2025",
        "GDCN",
        "Trình diễn công nghệ",
        "Trình diễn công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 9, 11),
        date(2025, 9, 11),
        "Sàn giao dịch công nghệ TP.HCM (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("bach-khoa",),
        doi_tuong=HAI,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "gdcn-cafe-2025",
        "GDCN",
        "Cafe công nghệ",
        "Cafe công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 6, 5),
        date(2025, 6, 5),
        "Không gian sáng tạo Trung tâm (địa điểm mẫu)",
        TT,
        D,
        partners=("hiep-hoi",),
        doi_tuong=DOI_TUONG,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "gdcn-tl-2025",
        "GDCN",
        "Triển lãm Sàn GDCN tham gia",
        "Triển lãm Sàn GDCN tham gia 2025" + DEMO_SUFFIX,
        date(2025, 10, 16),
        date(2025, 10, 18),
        "Trung tâm Hội chợ và Triển lãm TP.HCM (địa điểm mẫu)",
        TT,
        D,
        partners=("hiep-hoi",),
        doi_tuong=DOI_TUONG,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
    _a(
        "tttk-ht-2025",
        "TTTK",
        "Hội thảo xu hướng công nghệ",
        "Hội thảo xu hướng công nghệ 2025" + DEMO_SUFFIX,
        date(2025, 5, 22),
        date(2025, 5, 22),
        "Hội trường Trung tâm Thông tin – Thống kê (địa điểm mẫu)",
        KET_HOP,
        D,
        partners=("bach-khoa",),
        doi_tuong=DOI_TUONG,
        phieu_status=TrangThaiPhieu.DA_DUYET,
        factor="0.90",
    ),
)


@dataclass(frozen=True)
class SupportSpec:
    loai_ho_tro: str
    ngay_ho_tro: date
    noi_dung: str
    so_chuyen_gia: Decimal = ZERO


@dataclass(frozen=True)
class ProjectSpec:
    key: str
    phong: str
    ten: str
    chuong_trinh: str
    hinh_thuc: str
    nam: int
    supports: tuple[SupportSpec, ...]
    phieu_status: str


def _s(loai: str, day: date, noi_dung: str, experts: str = "0") -> SupportSpec:
    return SupportSpec(
        loai_ho_tro=loai,
        ngay_ho_tro=day,
        noi_dung=noi_dung,
        so_chuyen_gia=_d(experts),
    )


PROJECT_SPECS = (
    ProjectSpec(
        key="du-an-xanh",
        phong="HTKN",
        ten="Dự án ươm tạo công nghệ xanh" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ20,
        hinh_thuc=HinhThucDuAn.UOM_TAO,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.NGAY_CONG,
                date(2026, 3, 20),
                "Hỗ trợ ngày công kỹ thuật cho nhóm hoàn thiện mẫu thử.",
            ),
            _s(
                LoaiHoTro.CHUYEN_GIA,
                date(2026, 4, 10),
                "Kết nối chuyên gia về vật liệu và quy trình sản xuất.",
                "2",
            ),
            _s(
                LoaiHoTro.DICH_VU,
                date(2026, 9, 10),
                "Tư vấn hoàn thiện mô hình kinh doanh và hồ sơ gọi vốn.",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    ProjectSpec(
        key="du-an-so",
        phong="HTKN",
        ten="Dự án tăng tốc chuyển đổi số" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ64,
        hinh_thuc=HinhThucDuAn.TANG_TOC,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.CHUYEN_GIA,
                date(2026, 5, 15),
                "Kết nối chuyên gia thiết kế kiến trúc dữ liệu.",
                "3",
            ),
            _s(
                LoaiHoTro.DICH_VU,
                date(2026, 9, 15),
                "Tư vấn lộ trình chuyển đổi số và an toàn thông tin.",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    ProjectSpec(
        key="du-an-nong-nghiep",
        phong="HTKN",
        ten="Dự án nông nghiệp thông minh" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ20,
        hinh_thuc=HinhThucDuAn.UOM_TAO,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.NGAY_CONG,
                date(2026, 6, 5),
                "Hỗ trợ ngày công thử nghiệm cảm biến tại vườn mẫu.",
            ),
            _s(
                LoaiHoTro.CHUYEN_GIA,
                date(2026, 8, 20),
                "Kết nối chuyên gia nông nghiệp và tự động hóa.",
                "2",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    ProjectSpec(
        key="du-an-ngoai-nq20",
        phong="HTKN",
        ten="Dự án ngoài ngân sách NQ20" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NGOAI_NQ20,
        hinh_thuc=HinhThucDuAn.UOM_TAO,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.KHAC,
                date(2026, 7, 5),
                "Hỗ trợ kết nối đối tác và không gian làm việc.",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    ProjectSpec(
        key="du-an-vat-lieu",
        phong="HTKN",
        ten="Dự án vật liệu mới" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ64,
        hinh_thuc=HinhThucDuAn.TANG_TOC,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.NGAY_CONG,
                date(2026, 10, 10),
                "Hỗ trợ ngày công hoàn thiện bộ hồ sơ kỹ thuật.",
            ),
            _s(
                LoaiHoTro.DICH_VU,
                date(2026, 10, 12),
                "Tư vấn đánh giá tiềm năng thương mại hóa.",
            ),
        ),
        phieu_status=TrangThaiPhieu.CHO_DUYET,
    ),
    ProjectSpec(
        key="du-an-2025",
        phong="HTKN",
        ten="Dự án ươm tạo 2025" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ20,
        hinh_thuc=HinhThucDuAn.UOM_TAO,
        nam=2025,
        supports=(
            _s(
                LoaiHoTro.NGAY_CONG,
                date(2025, 5, 10),
                "Hỗ trợ ngày công kỹ thuật cho dự án năm 2025.",
            ),
            _s(
                LoaiHoTro.CHUYEN_GIA,
                date(2025, 6, 10),
                "Kết nối chuyên gia tư vấn thị trường.",
                "1",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
    ProjectSpec(
        key="gdcn-du-an-ket-noi",
        phong="GDCN",
        ten="Dự án kết nối cung cầu công nghệ" + DEMO_SUFFIX,
        chuong_trinh=ChuongTrinhDuAn.NQ20,
        hinh_thuc=HinhThucDuAn.TANG_TOC,
        nam=2026,
        supports=(
            _s(
                LoaiHoTro.DICH_VU,
                date(2026, 9, 12),
                "Tư vấn kết nối cung cầu cho doanh nghiệp trong sàn.",
            ),
        ),
        phieu_status=TrangThaiPhieu.DA_DUYET,
    ),
)

SUPPLEMENTAL_SPECS = (
    {
        "activity_key": "htkn-lop-2",
        "factor": _d("0.20"),
        "status": TrangThaiPhieu.DA_DUYET,
    },
)

# Base values for the activity form templates. The seed multiplies each base by
# the activity factor, preserving the parent/child caps in the catalog.
ACTIVITY_BASES = {
    "HTKN-LOP-HV": _d("30"),
    "HTKN-LOP-CN": _d("24"),
    "HTKN-LOP-CG": _d("4"),
    "HTKN-LOP-KS": _d("20"),
    "HTKN-HN-ND": _d("110"),
    "HTKN-HN-CG": _d("7"),
    "HTKN-TL-GH": _d("60"),
    "HTKN-TL-SP": _d("120"),
    "HTKN-TL-LQ": _d("3000"),
    "HTKN-TL-CG": _d("10"),
    "HTKN-TL-KS": _d("30"),
    "GDCN-TM-GH": _d("80"),
    "GDCN-TM-HT": _d("4"),
    "GDCN-TM-CG": _d("12"),
    "GDCN-TM-KH": _d("350"),
    "GDCN-TM-BB": _d("20"),
    "GDCN-MOU": _d("4"),
    "GDCN-BB": _d("6"),
    "GDCN-HD": _d("3"),
    "GDCN-GT": _d("2000000000"),
    "GDCN-TD-CG": _d("8"),
    "GDCN-TD-DVTD": _d("12"),
    "GDCN-TD-DVTB": _d("15"),
    "GDCN-TD-CNTB": _d("45"),
    "GDCN-TD-KTT": _d("180"),
    "GDCN-TD-KTL": _d("220"),
    "GDCN-TD-LIVE": _d("1500"),
    "GDCN-TD-HOTRO": _d("54"),
    "GDCN-TD-KHACH": _d("270"),
    "GDCN-YC-TRINH-DIEN": _d("30"),
    "GDCN-YC-KT": _d("8"),
    "GDCN-TD-TC": _d("4000"),
    "GDCN-CAFE-DV": _d("20"),
    "GDCN-CAFE-KTT": _d("80"),
    "GDCN-CAFE-KTL": _d("60"),
    "GDCN-CAFE-LIVE": _d("900"),
    "GDCN-YC-CAFE": _d("15"),
    "GDCN-CAFE-TC": _d("2200"),
    "GDCN-TINH-DV": _d("30"),
    "GDCN-TINH-CNTB": _d("50"),
    "GDCN-TL-CNTB-DN": _d("30"),
    "GDCN-TL-KQ-VT": _d("8"),
    "GDCN-HT-KQ": _d("2"),
    "GDCN-KN-SP": _d("5"),
    "TTTK-HT-DK": _d("120"),
    "TTTK-HT-TT": _d("100"),
    "TTTK-HT-HL": _d("4.0"),
    "TTTK-HT-NHU-CAU": _d("60"),
    "TTTK-HT-CG": _d("12"),
}

MONTHLY_BASES = {
    "GDCN-HS": _d("12"),
    "GDCN-TB": _d("40"),
    "GDCN-CG": _d("4"),
    "GDCN-TSTT": _d("2"),
    "GDCN-DVCU": _d("4"),
    "GDCN-LT": _d("15000"),
    "GDCN-USER": _d("120"),
    "GDCN-YC-TECHPORT": _d("4"),
    "GDCN-KNCC": _d("15"),
    "GDCN-BV": _d("10"),
    "GDCN-TC-TT": _d("3000"),
    "GDCN-TB-SAN": _d("8"),
    "GDCN-VH-TC": _d("2500"),
    "TTTK-NDT": _d("38"),
    "TTTK-TIN-HT": _d("160"),
    "TTTK-HD-SHCN": _d("9"),
    "TTTK-DON-DK": _d("32"),
    "TTTK-DON-CB": _d("24"),
    "TTTK-DON-CAP": _d("16"),
    "TTTK-BM": _d("1"),
    "TTTK-VB-BC": _d("10"),
    "TTTK-PHIEU": _d("85"),
    "TTTK-VB-DT": _d("1"),
    "TTTK-RD-NHAN-LUC": _d("220"),
    "TTTK-RD-NHA-NC": _d("155"),
    "TTTK-RD-CHI": _d("4200000000"),
    "TTTK-RD-NV": _d("5"),
    "TTTK-WEB-LUOT": _d("9500"),
    "TTTK-WEB-ND": _d("2400"),
    "TTTK-LK-DV": _d("6"),
    "TTTK-LK-TL": _d("38"),
    "TTTK-LK-LUOT": _d("4500"),
    "TTTK-HT-TC": _d("400"),
}

MONTH_FACTORS = (
    _d("0.85"),
    _d("0.90"),
    _d("1.00"),
    _d("0.95"),
    _d("1.05"),
    _d("1.10"),
    _d("0.80"),
    _d("1.00"),
    _d("1.15"),
    _d("1.05"),
    _d("0.90"),
    _d("1.00"),
)

OBJECT_WEIGHTS = {
    "GDCN-TD-HOTRO": {"Viện/trường": _d("18"), "Doanh nghiệp": _d("90")},
}

# Current-year and previous-year plans. Codes not listed keep the values that
# seed_catalog creates and are only confirmed.
PLAN_SPECS = {
    "HTKN-LOP": (_d("6"), _d("4")),
    "HTKN-LOP-HV": (_d("160"), _d("120")),
    "HTKN-LOP-CN": (_d("130"), _d("100")),
    "HTKN-LOP-CG": (_d("20"), _d("16")),
    "HTKN-LOP-KS": (_d("110"), _d("85")),
    "HTKN-HN": (_d("3"), _d("2")),
    "HTKN-HN-ND": (_d("300"), _d("240")),
    "HTKN-HN-CG": (_d("20"), _d("16")),
    "HTKN-TL": (_d("2"), _d("1")),
    "HTKN-TL-GH": (_d("80"), _d("60")),
    "HTKN-TL-SP": (_d("160"), _d("120")),
    "HTKN-TL-LQ": (_d("4000"), _d("3000")),
    "HTKN-TL-CG": (_d("14"), _d("10")),
    "HTKN-TL-KS": (_d("40"), _d("30")),
    "HTKN-DA-NC": (_d("3"), _d("2")),
    "HTKN-DA-CG": (_d("4"), _d("3")),
    "HTKN-DA-DV": (_d("3"), _d("2")),
    "HTKN-DA-NGOAI": (_d("1"), _d("1")),
    "GDCN-TM": (_d("2"), _d("2")),
    "GDCN-TD": (_d("3"), _d("2")),
    "GDCN-CAFE": (_d("2"), _d("2")),
    "GDCN-TINH-TQ": (_d("2"), _d("2")),
    "GDCN-TINH-PN": (_d("2"), _d("1")),
    "GDCN-GT": (_d("12000000000"), _d("10000000000")),
    "GDCN-USER": (_d("1200"), _d("1000")),
    "GDCN-KNCC": (_d("150"), _d("120")),
    "GDCN-TC-TT": (_d("30000"), _d("25000")),
    "GDCN-VH-TC": (_d("25000"), _d("20000")),
    "GDCN-TD-TC": (_d("40000"), _d("32000")),
    "TTTK-NDT": (_d("450"), _d("380")),
    "TTTK-TIN-HT": (_d("1700"), _d("1450")),
    "TTTK-HD-SHCN": (_d("100"), _d("85")),
    "TTTK-DON-DK": (_d("340"), _d("290")),
    "TTTK-DON-CB": (_d("260"), _d("220")),
    "TTTK-DON-CAP": (_d("180"), _d("150")),
    "TTTK-BM": (_d("12"), _d("10")),
    "TTTK-VB-BC": (_d("110"), _d("95")),
    "TTTK-PHIEU": (_d("900"), _d("760")),
    "TTTK-VB-DT": (_d("12"), _d("10")),
    "TTTK-RD-NHAN-LUC": (_d("250"), _d("215")),
    "TTTK-RD-NHA-NC": (_d("180"), _d("155")),
    "TTTK-RD-CHI": (_d("5000000000"), _d("4300000000")),
    "TTTK-RD-NV": (_d("6"), _d("5")),
    "TTTK-WEB-LUOT": (_d("100000"), _d("85000")),
    "TTTK-WEB-ND": (_d("25000"), _d("21000")),
    "TTTK-LK-DV": (_d("70"), _d("60")),
    "TTTK-LK-TL": (_d("420"), _d("360")),
    "TTTK-LK-LUOT": (_d("50000"), _d("43000")),
    "TTTK-HT-TC": (_d("4500"), _d("3900")),
    "TTTK-HT-DK": (_d("250"), _d("220")),
    "TTTK-HT-TT": (_d("220"), _d("190")),
    "TTTK-HT-HL": (_d("4.5"), _d("4.2")),
    "TTTK-HT-NHU-CAU": (_d("130"), _d("110")),
    "TTTK-HT-CG": (_d("26"), _d("22")),
}


@dataclass
class Catalog:
    phong: dict[str, PhongBan]
    users: dict[str, User]
    objects: dict[str, DanhMucDoiTuong]
    sources: dict[str, NguonSoLieu]
    activity_types: dict[tuple[str, str], LoaiHoatDong]
    indicators: dict[str, ChiTieu]
    fields: dict[str, DanhMucLinhVuc]
    partners: dict[str, DonViPhoiHop]

    def entry_user(self, ma_phong: str) -> User:
        return self.users[f"cb.{ma_phong.lower()}"]

    def head_user(self, ma_phong: str) -> User:
        return self.users[f"ld.{ma_phong.lower()}"]


# ---------------------------------------------------------------------------
# Generic idempotent helpers
# ---------------------------------------------------------------------------


def _ensure(model, lookup, values, *, history_user=None, history_date=None):
    obj = model.objects.filter(**lookup).first()
    created = obj is None
    if created:
        obj = model(**lookup)
    changed = False
    for name, value in values.items():
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            changed = True
    if created or changed:
        if history_user is not None:
            obj._history_user = history_user
        if history_date is not None:
            obj._history_date = history_date
        obj.save()
    return obj, created, changed


def _assign_m2m(obj, field_name, targets) -> bool:
    desired = {target.pk for target in targets}
    current = set(getattr(obj, field_name).values_list("pk", flat=True))
    if current == desired:
        return False
    getattr(obj, field_name).set(desired)
    return True


def _distribute(total: Decimal, weights: list[Decimal]) -> list[Decimal]:
    total = _q(total)
    total_weight = sum(weights, ZERO)
    parts = []
    remaining = total
    for index, weight in enumerate(weights):
        if index == len(weights) - 1:
            part = remaining
        else:
            part = _q(total * weight / total_weight)
            remaining -= part
        parts.append(part)
    return parts


def _object_options(chi_tieu: ChiTieu) -> list[DanhMucDoiTuong]:
    applicable = list(chi_tieu.doi_tuong_ap_dung.all().order_by("ten_doi_tuong"))
    if applicable:
        return applicable
    return list(DanhMucDoiTuong.objects.all().order_by("ten_doi_tuong")[:4])


def _pick_source(chi_tieu: ChiTieu):
    return chi_tieu.nguon_cho_phep.all().order_by("ten_nguon").first()


def _write_indicator(
    phieu: PhieuNhapLieu,
    chi_tieu: ChiTieu,
    total: Decimal,
    user: User,
    when: datetime,
    *,
    fields: dict[str, DanhMucLinhVuc],
) -> None:
    total = _q(total)
    source = _pick_source(chi_tieu)
    _ensure(
        SoLieu,
        {
            "phieu": phieu,
            "chi_tieu": chi_tieu,
            "doi_tuong": None,
            "linh_vuc": None,
        },
        {"gia_tri": total, "nguon": source, "ghi_chu": ""},
        history_user=user,
        history_date=when,
    )

    if chi_tieu.phan_loai_doi_tuong:
        objects = _object_options(chi_tieu)
        if chi_tieu.cach_tong_hop == CachTongHop.AVERAGE:
            objects = objects[:2]
        if objects:
            weights = [
                OBJECT_WEIGHTS.get(chi_tieu.ma_chi_tieu, {}).get(
                    obj.ten_doi_tuong,
                    _d("1"),
                )
                for obj in objects
            ]
            parts = _distribute(total, weights)
            for obj, value in zip(objects, parts):
                _ensure(
                    SoLieu,
                    {
                        "phieu": phieu,
                        "chi_tieu": chi_tieu,
                        "doi_tuong": obj,
                        "linh_vuc": None,
                    },
                    {"gia_tri": value, "nguon": None, "ghi_chu": ""},
                    history_user=user,
                    history_date=when,
                )

    if chi_tieu.phan_loai_linh_vuc:
        selected_fields = [fields["MAU-01"], fields["MAU-02"]]
        parts = _distribute(total, [_d("1"), _d("1")])
        for linh_vuc, value in zip(selected_fields, parts):
            _ensure(
                SoLieu,
                {
                    "phieu": phieu,
                    "chi_tieu": chi_tieu,
                    "doi_tuong": None,
                    "linh_vuc": linh_vuc,
                },
                {"gia_tri": value, "nguon": None, "ghi_chu": ""},
                history_user=user,
                history_date=when,
            )


def _activity_indicators(activity: HoatDong):
    return (
        BieuMauChiTieu.objects.filter(
            loai_hoat_dong=activity.loai_hoat_dong,
            chi_tieu__dang_su_dung=True,
        )
        .select_related("chi_tieu")
        .order_by("thu_tu", "id")
    )


def _write_activity_rows(
    phieu: PhieuNhapLieu,
    activity: HoatDong,
    factor: Decimal,
    user: User,
    when: datetime,
    *,
    fields: dict[str, DanhMucLinhVuc],
    missing_code: str | None = None,
) -> None:
    if activity.la_nhiem_vu_phat_sinh:
        return
    for form_row in _activity_indicators(activity):
        chi_tieu = form_row.chi_tieu
        code = chi_tieu.ma_chi_tieu
        if code == missing_code:
            continue
        base = ACTIVITY_BASES.get(code, _d("1"))
        total = _q(base * factor)
        if chi_tieu.cach_tong_hop == CachTongHop.AVERAGE:
            total = min(max(total, _d("1")), _d("5"))
        _write_indicator(phieu, chi_tieu, total, user, when, fields=fields)


def _write_monthly_rows(
    phieu: PhieuNhapLieu,
    phong: PhongBan,
    ky: KyBaoCao,
    factor: Decimal,
    user: User,
    when: datetime,
    *,
    fields: dict[str, DanhMucLinhVuc],
    missing_code: str | None = None,
) -> None:
    indicators = (
        ChiTieu.objects.filter(
            nhom__phong=phong,
            kieu_ghi_nhan=KieuGhiNhan.MONTH,
            dang_su_dung=True,
        )
        .exclude(cach_tong_hop__in=(CachTongHop.RATIO, CachTongHop.COUNT))
        .order_by("nhom__thu_tu", "ma_chi_tieu")
    )
    for chi_tieu in indicators:
        code = chi_tieu.ma_chi_tieu
        if code == missing_code:
            continue
        base = MONTHLY_BASES.get(code)
        if base is None:
            continue
        if chi_tieu.cach_tong_hop == CachTongHop.LATEST:
            growth = _d("1") + _d("0.012") * Decimal(ky.so_ky - 1)
            total = base * growth * factor
        else:
            total = base * MONTH_FACTORS[ky.so_ky - 1] * factor
        _write_indicator(phieu, chi_tieu, total, user, when, fields=fields)


# ---------------------------------------------------------------------------
# Workflow helpers
# ---------------------------------------------------------------------------


def _new_phieu(
    *,
    phong: PhongBan,
    loai_phieu: str,
    nguoi_nhap: User,
    created_at: datetime,
    hoat_dong: HoatDong | None = None,
    ky: KyBaoCao | None = None,
    du_an: DuAn | None = None,
    la_phieu_bo_sung: bool = False,
) -> PhieuNhapLieu:
    phieu = PhieuNhapLieu(
        phong=phong,
        loai_phieu=loai_phieu,
        hoat_dong=hoat_dong,
        ky=ky,
        du_an=du_an,
        la_phieu_bo_sung=la_phieu_bo_sung,
        trang_thai=TrangThaiPhieu.NHAP,
        nguoi_nhap=nguoi_nhap,
    )
    phieu._history_user = nguoi_nhap
    phieu._history_date = created_at
    phieu._change_reason = "Tạo phiếu dữ liệu mẫu"
    phieu.save()
    return phieu


def _transition_seed(
    phieu: PhieuNhapLieu,
    action: str,
    user: User,
    when: datetime,
    *,
    comment: str = "",
) -> None:
    row = LichSuXuLy.objects.create(
        phieu=phieu,
        nguoi_xu_ly=user,
        hanh_dong=action,
        y_kien=comment,
    )
    LichSuXuLy.objects.filter(pk=row.pk).update(thoi_diem=when)

    update_fields = ["trang_thai"]
    if action == HanhDongXuLy.GUI:
        phieu.trang_thai = TrangThaiPhieu.CHO_DUYET
        phieu.ngay_gui = when
        update_fields.append("ngay_gui")
    elif action == HanhDongXuLy.DUYET:
        phieu.trang_thai = TrangThaiPhieu.DA_DUYET
    elif action == HanhDongXuLy.TRA_LAI:
        phieu.trang_thai = TrangThaiPhieu.TRA_LAI
    elif action == HanhDongXuLy.MO_LAI:
        phieu.trang_thai = TrangThaiPhieu.NHAP
    phieu._change_reason = TrangThaiPhieu(phieu.trang_thai).label
    phieu._history_user = user
    phieu._history_date = when
    phieu.save(update_fields=update_fields)


def _apply_status(
    phieu: PhieuNhapLieu,
    status: str,
    *,
    entry_user: User,
    head_user: User,
    sent_at: datetime,
    decided_at: datetime,
    after_send=None,
    return_comment: str = RETURN_COMMENT,
    reopen_comment: str = REOPEN_COMMENT,
) -> None:
    if status == TrangThaiPhieu.NHAP:
        return
    _transition_seed(phieu, HanhDongXuLy.GUI, entry_user, sent_at)
    if after_send is not None:
        after_send(sent_at + timedelta(hours=3))
    if status == TrangThaiPhieu.CHO_DUYET:
        return
    if status == TrangThaiPhieu.DA_DUYET:
        _transition_seed(phieu, HanhDongXuLy.DUYET, head_user, decided_at)
        return
    if status == TrangThaiPhieu.TRA_LAI:
        _transition_seed(
            phieu,
            HanhDongXuLy.TRA_LAI,
            head_user,
            decided_at,
            comment=return_comment,
        )
        return
    if status == "mo_lai":
        _transition_seed(phieu, HanhDongXuLy.DUYET, head_user, decided_at)
        _transition_seed(
            phieu,
            HanhDongXuLy.MO_LAI,
            head_user,
            decided_at + timedelta(days=1),
            comment=reopen_comment,
        )
        return
    raise CommandError(f"Trạng thái phiếu mẫu không hợp lệ: {status}")


def _validate_complete(phieu: PhieuNhapLieu) -> None:
    errors = workflow.submission_errors(phieu)
    if errors:
        raise CommandError(
            f"Phiếu mẫu {phieu.pk} không hợp lệ theo biểu mẫu: "
            + "; ".join(errors)
        )


# ---------------------------------------------------------------------------
# Catalog and period helpers
# ---------------------------------------------------------------------------


def assert_local_database() -> None:
    db = connection.settings_dict
    host = db.get("HOST") or ""
    name = db.get("NAME") or ""
    user = db.get("USER") or ""
    port = str(db.get("PORT") or "")
    if db.get("ENGINE") != "django.db.backends.postgresql":
        raise CommandError("Chỉ chạy seed trên PostgreSQL localhost.")
    if host not in ("127.0.0.1", "localhost"):
        raise CommandError(f"Từ chối seed: host {host!r} không phải localhost.")
    if name != "solieu":
        raise CommandError(f"Từ chối seed: database {name!r} không phải 'solieu'.")
    if user != "solieu":
        raise CommandError(f"Từ chối seed: user {user!r} không phải 'solieu'.")
    if port != "5432":
        raise CommandError(f"Từ chối seed: port {port!r} không phải 5432.")
    if not settings.DEBUG:
        raise CommandError("Từ chối seed: DJANGO_DEBUG phải là true trên máy local.")


def build_catalog() -> Catalog:
    phong = {row.ma_phong: row for row in PhongBan.objects.all()}
    missing = [code for code in ("GDCN", "TTTK", "HTKN", "BGĐ") if code not in phong]
    if missing:
        raise CommandError("Thiếu phòng ban: " + ", ".join(missing))
    users = {user.username: user for user in User.objects.all()}
    objects = {row.ten_doi_tuong: row for row in DanhMucDoiTuong.objects.all()}
    sources = {row.ten_nguon: row for row in NguonSoLieu.objects.all()}
    activity_types = {
        (row.phong.ma_phong, row.ten_loai): row
        for row in LoaiHoatDong.objects.select_related("phong")
    }
    indicators = {row.ma_chi_tieu: row for row in ChiTieu.objects.all()}
    fields = {row.ma: row for row in DanhMucLinhVuc.objects.all()}
    for code in ("MAU-01", "MAU-02"):
        if code not in fields:
            raise CommandError(
                "Chưa nạp fixtures/linh_vuc.csv. Chạy load_linh_vuc trước."
            )
    partners = {}
    for key, (name, object_name) in PARTNER_UNITS.items():
        obj = objects.get(object_name)
        partner, _created, _changed = _ensure(
            DonViPhoiHop,
            {"ten_don_vi": name},
            {"doi_tuong": obj},
        )
        partners[key] = partner
    return Catalog(
        phong=phong,
        users=users,
        objects=objects,
        sources=sources,
        activity_types=activity_types,
        indicators=indicators,
        fields=fields,
        partners=partners,
    )


def _ensure_periods() -> dict[tuple[int, int], KyBaoCao]:
    periods = {}
    for year in (PREVIOUS_YEAR, DEMO_YEAR):
        for month in range(1, 13):
            if year == PREVIOUS_YEAR or month <= 10:
                status = TrangThaiKy.KHOA
            else:
                status = TrangThaiKy.MO
            first_day = date(year, month, 1)
            last_day = _month_end(year, month)
            row = KyBaoCao.objects.filter(nam=year, so_ky=month).first()
            created = row is None
            if created:
                row = KyBaoCao(nam=year, so_ky=month)
            changed = created or row.tu_ngay != first_day or row.den_ngay != last_day
            if created:
                row.trang_thai = status
            if changed:
                row.save()
            periods[(year, month)] = row
    return periods


def _ensure_plan(
    chi_tieu: ChiTieu,
    nam: int,
    doi_tuong: DanhMucDoiTuong | None,
    value: Decimal,
    status: str,
) -> None:
    row = ChiTieuKeHoach.objects.filter(
        chi_tieu=chi_tieu,
        nam=nam,
        doi_tuong=doi_tuong,
    ).first()
    created = row is None
    if created:
        row = ChiTieuKeHoach(
            chi_tieu=chi_tieu,
            nam=nam,
            doi_tuong=doi_tuong,
        )
    old_value = None if created else row.gia_tri_ke_hoach
    old_status = None if created else row.trang_thai
    changed = created
    if row.gia_tri_ke_hoach != value:
        row.gia_tri_ke_hoach = value
        changed = True
    if row.trang_thai != status:
        row.trang_thai = status
        changed = True
    if (
        old_status == TrangThaiKeHoach.DA_XAC_NHAN
        and old_value != value
    ):
        row.ly_do = f"Điều chỉnh kế hoạch dữ liệu mẫu thành {value}."
    if created or changed:
        row.save()


def _seed_plans(catalogs: Catalog) -> None:
    # Confirm the rows seed_catalog already created for the current year.
    for row in ChiTieuKeHoach.objects.filter(nam=DEMO_YEAR):
        if row.trang_thai != TrangThaiKeHoach.DA_XAC_NHAN:
            row.trang_thai = TrangThaiKeHoach.DA_XAC_NHAN
            row.save()

    for code, (current, _previous) in PLAN_SPECS.items():
        chi_tieu = catalogs.indicators[code]
        _ensure_plan(chi_tieu, DEMO_YEAR, None, current, TrangThaiKeHoach.DA_XAC_NHAN)

    current_rows = list(
        ChiTieuKeHoach.objects.filter(nam=DEMO_YEAR).select_related("chi_tieu")
    )
    for row in current_rows:
        code = row.chi_tieu.ma_chi_tieu
        if row.doi_tuong_id is None and code in PLAN_SPECS:
            previous_value = PLAN_SPECS[code][1]
        else:
            previous_value = _q((row.gia_tri_ke_hoach or ZERO) * _d("0.90"))
        _ensure_plan(
            row.chi_tieu,
            PREVIOUS_YEAR,
            row.doi_tuong,
            previous_value,
            TrangThaiKeHoach.DA_XAC_NHAN,
        )


# ---------------------------------------------------------------------------
# Activity, project, and monthly seeding
# ---------------------------------------------------------------------------


def _ensure_activity(spec: ActivitySpec, catalogs: Catalog) -> HoatDong:
    loai = catalogs.activity_types.get((spec.phong, spec.loai))
    if loai is None:
        raise CommandError(f"Không có loại hoạt động {spec.loai!r} của {spec.phong}.")
    user = catalogs.entry_user(spec.phong)
    created_at = _at(spec.tu_ngay - timedelta(days=14), 8, 30)
    activity, _created, _changed = _ensure(
        HoatDong,
        {"loai_hoat_dong": loai, "ten": spec.ten},
        {
            "tu_ngay": spec.tu_ngay,
            "den_ngay": spec.den_ngay,
            "dia_diem": spec.dia_diem,
            "hinh_thuc": spec.hinh_thuc,
            "trang_thai": spec.trang_thai,
            "linh_vuc": catalogs.fields.get(spec.linh_vuc),
            "noi_dung": spec.noi_dung,
            "ket_qua": spec.ket_qua,
        },
        history_user=user,
        history_date=created_at,
    )
    _assign_m2m(
        activity,
        "doi_tuong_huong_toi",
        [catalogs.objects[name] for name in spec.doi_tuong],
    )
    for key in spec.partners:
        partner = catalogs.partners[key]
        HoatDongDonVi.objects.get_or_create(
            hoat_dong=activity,
            don_vi=partner,
            defaults={"vai_tro": "Phối hợp"},
        )
    return activity


def _seed_activity_phieu(
    activity: HoatDong,
    spec: ActivitySpec,
    catalogs: Catalog,
) -> None:
    if spec.phieu_status is None:
        return
    existing = PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.HOAT_DONG,
        hoat_dong=activity,
        la_phieu_bo_sung=False,
    ).first()
    if existing is not None:
        return
    entry_user = catalogs.entry_user(spec.phong)
    head_user = catalogs.head_user(spec.phong)
    created_at = _at(spec.den_ngay + timedelta(days=1), 16, 0)
    sent_at = _at(spec.den_ngay + timedelta(days=2), 9, 0)
    decided_at = _at(spec.den_ngay + timedelta(days=4), 10, 0)
    phieu = _new_phieu(
        phong=activity.phong,
        loai_phieu=LoaiPhieu.HOAT_DONG,
        nguoi_nhap=entry_user,
        created_at=created_at,
        hoat_dong=activity,
    )
    _write_activity_rows(
        phieu,
        activity,
        spec.factor,
        entry_user,
        created_at,
        fields=catalogs.fields,
        missing_code=spec.missing_code,
    )

    def after_send(when: datetime) -> None:
        _write_activity_rows(
            phieu,
            activity,
            spec.factor * _d("1.10"),
            entry_user,
            when,
            fields=catalogs.fields,
        )

    _apply_status(
        phieu,
        spec.phieu_status,
        entry_user=entry_user,
        head_user=head_user,
        sent_at=sent_at,
        decided_at=decided_at,
        after_send=after_send if spec.changed_after_send else None,
    )
    if spec.phieu_status != TrangThaiPhieu.NHAP:
        _validate_complete(phieu)


def _seed_supplemental(spec: dict, catalogs: Catalog) -> None:
    activity = HoatDong.objects.filter(
        loai_hoat_dong__phong__ma_phong="HTKN",
        ten__startswith="Lớp huấn luyện kỹ năng số cho doanh nghiệp – đợt 2",
    ).first()
    if activity is None:
        return
    existing = PhieuNhapLieu.objects.filter(
        loai_phieu=LoaiPhieu.HOAT_DONG,
        hoat_dong=activity,
        la_phieu_bo_sung=True,
        nguoi_nhap=catalogs.entry_user("HTKN"),
    ).first()
    if existing is not None:
        return
    entry_user = catalogs.entry_user("HTKN")
    head_user = catalogs.head_user("HTKN")
    created_at = _at(date(2026, 4, 20), 16, 0)
    sent_at = _at(date(2026, 4, 21), 9, 0)
    decided_at = _at(date(2026, 4, 22), 10, 0)
    phieu = _new_phieu(
        phong=activity.phong,
        loai_phieu=LoaiPhieu.HOAT_DONG,
        nguoi_nhap=entry_user,
        created_at=created_at,
        hoat_dong=activity,
        la_phieu_bo_sung=True,
    )
    _write_activity_rows(
        phieu,
        activity,
        spec["factor"],
        entry_user,
        created_at,
        fields=catalogs.fields,
    )
    _apply_status(
        phieu,
        spec["status"],
        entry_user=entry_user,
        head_user=head_user,
        sent_at=sent_at,
        decided_at=decided_at,
    )
    _validate_complete(phieu)


def _seed_projects(catalogs: Catalog) -> None:
    for spec in PROJECT_SPECS:
        phong = catalogs.phong[spec.phong]
        entry_user = catalogs.entry_user(spec.phong)
        head_user = catalogs.head_user(spec.phong)
        created_at = _at(date(spec.nam, 1, 15), 8, 0)
        project, _created, _changed = _ensure(
            DuAn,
            {"phong": phong, "ten_du_an": spec.ten, "nam": spec.nam},
            {
                "chuong_trinh": spec.chuong_trinh,
                "hinh_thuc": spec.hinh_thuc,
            },
            history_user=entry_user,
            history_date=created_at,
        )
        phieu = PhieuNhapLieu.objects.filter(
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=project,
            la_phieu_bo_sung=False,
        ).first()
        if phieu is not None:
            continue
        phieu_created = _at(spec.supports[0].ngay_ho_tro - timedelta(days=2), 16, 0)
        sent_at = _at(spec.supports[0].ngay_ho_tro - timedelta(days=1), 9, 0)
        decided_at = _at(spec.supports[0].ngay_ho_tro + timedelta(days=1), 10, 0)
        phieu = _new_phieu(
            phong=phong,
            loai_phieu=LoaiPhieu.DU_AN,
            nguoi_nhap=entry_user,
            created_at=phieu_created,
            du_an=project,
        )
        for support in spec.supports:
            _ensure(
                HoTroDuAn,
                {
                    "du_an": project,
                    "phieu": phieu,
                    "loai_ho_tro": support.loai_ho_tro,
                    "ngay_ho_tro": support.ngay_ho_tro,
                    "noi_dung": support.noi_dung,
                },
                {"so_chuyen_gia": support.so_chuyen_gia},
                history_user=entry_user,
                history_date=phieu_created,
            )
        _apply_status(
            phieu,
            spec.phieu_status,
            entry_user=entry_user,
            head_user=head_user,
            sent_at=sent_at,
            decided_at=decided_at,
        )
        if spec.phieu_status != TrangThaiPhieu.NHAP:
            _validate_complete(phieu)


def _month_status(phong_code: str, year: int, month: int) -> str | None:
    if year == PREVIOUS_YEAR or month <= 10:
        return TrangThaiPhieu.DA_DUYET
    if month == 11:
        if phong_code == "GDCN":
            return TrangThaiPhieu.NHAP
        if phong_code == "TTTK":
            return TrangThaiPhieu.CHO_DUYET
        return TrangThaiPhieu.DA_DUYET
    return None


def _seed_monthly(catalogs: Catalog, periods: dict[tuple[int, int], KyBaoCao]) -> None:
    for year in (PREVIOUS_YEAR, DEMO_YEAR):
        for month in range(1, 13):
            ky = periods[(year, month)]
            for phong_code in ("GDCN", "TTTK", "HTKN"):
                status = _month_status(phong_code, year, month)
                if status is None:
                    continue
                phong = catalogs.phong[phong_code]
                entry_user = catalogs.entry_user(phong_code)
                head_user = catalogs.head_user(phong_code)
                phieu = PhieuNhapLieu.objects.filter(
                    loai_phieu=LoaiPhieu.THANG,
                    phong=phong,
                    ky=ky,
                    la_phieu_bo_sung=False,
                ).first()
                if phieu is not None:
                    continue
                if year == DEMO_YEAR and month == 11:
                    created_day = date(2026, 11, 10)
                else:
                    created_day = _month_end(year, month)
                created_at = _at(created_day, 16, 0)
                sent_at = _at(created_day + timedelta(days=1), 9, 0)
                decided_at = _at(created_day + timedelta(days=2), 10, 0)
                phieu = _new_phieu(
                    phong=phong,
                    loai_phieu=LoaiPhieu.THANG,
                    nguoi_nhap=entry_user,
                    created_at=created_at,
                    ky=ky,
                )
                factor = _d("0.80") if year == PREVIOUS_YEAR else _d("1")
                missing_code = (
                    "GDCN-TC-TT"
                    if phong_code == "GDCN"
                    and year == DEMO_YEAR
                    and month == 11
                    else None
                )
                _write_monthly_rows(
                    phieu,
                    phong,
                    ky,
                    factor,
                    entry_user,
                    created_at,
                    fields=catalogs.fields,
                    missing_code=missing_code,
                )
                _apply_status(
                    phieu,
                    status,
                    entry_user=entry_user,
                    head_user=head_user,
                    sent_at=sent_at,
                    decided_at=decided_at,
                )
                if status != TrangThaiPhieu.NHAP:
                    _validate_complete(phieu)


# ---------------------------------------------------------------------------
# Published reports
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ReportSpec:
    year: int
    month: int | None
    phong_code: str | None
    dinh_dang: str
    username: str
    accepted: bool = False
    annual: bool = False


REPORT_SPECS = (
    ReportSpec(DEMO_YEAR, 9, "GDCN", "xlsx", "ld.gdcn"),
    ReportSpec(DEMO_YEAR, 9, "TTTK", "docx", "ld.tttk"),
    ReportSpec(DEMO_YEAR, 9, "HTKN", "xlsx", "ld.htkn"),
    ReportSpec(DEMO_YEAR, 9, None, "xlsx", "ld.tt"),
    ReportSpec(DEMO_YEAR, 9, None, "docx", "ld.tt"),
    ReportSpec(DEMO_YEAR, 10, None, "xlsx", "ld.tt", accepted=True),
    ReportSpec(PREVIOUS_YEAR, None, None, "xlsx", "ld.tt", annual=True),
)


def _seed_reports(catalogs: Catalog) -> None:
    for spec in REPORT_SPECS:
        if spec.annual:
            period = resolve_period(KIND_YEAR, spec.year)
        else:
            period = resolve_period(KIND_MONTH, spec.year, month=spec.month)
        label = period_label(period)
        phong = catalogs.phong[spec.phong_code] if spec.phong_code else None
        user = catalogs.users[spec.username]
        existing = BaoCaoDaXuat.objects.filter(
            ky=label,
            phong=phong,
            dinh_dang=spec.dinh_dang,
        ).first()
        if (
            existing is not None
            and existing.file
            and existing.file.storage.exists(existing.file.name)
            and existing.dong.exists()
        ):
            continue
        if existing is not None:
            existing.file.delete(save=False)
            existing.delete()

        departments = (
            [phong]
            if phong is not None
            else [catalogs.phong[code] for code in ("GDCN", "TTTK", "HTKN")]
        )
        rows_by_department = rollup_by_department(period, departments)
        gaps_by_department = collect_gaps(period, departments)
        reports, _gaps = build_department_reports(
            period=period,
            departments=departments,
            notes={},
            accepted=spec.accepted,
            rows_by_department=rows_by_department,
            gaps_by_department=gaps_by_department,
        )
        if spec.dinh_dang == "xlsx":
            content = build_workbook(
                reports,
                period_label=label,
                accepted=spec.accepted,
            )
        else:
            content = build_docx(
                reports,
                period_label=label,
                accepted=spec.accepted,
                user_label=user.ho_ten or user.username,
                is_center=phong is None,
            )
        filename = export_filename(period, phong, spec.dinh_dang)
        create_export_record(
            period_label=label,
            phong=phong,
            user=user,
            dinh_dang=spec.dinh_dang,
            filename=filename,
            content=content,
            reports=reports,
            accepted=spec.accepted,
        )


# ---------------------------------------------------------------------------
# Counts and entry point
# ---------------------------------------------------------------------------


def _tracked_models():
    for app_label in ("accounts", "catalog", "activities", "entry", "reporting"):
        for model in apps.get_app_config(app_label).get_models():
            if model._meta.model_name.startswith("historical"):
                continue
            yield model


def _counts() -> dict[str, int]:
    return {
        model._meta.db_table: model.objects.count()
        for model in _tracked_models()
    }


def _count_lines() -> list[str]:
    lines = ["Số dòng bảng nghiệp vụ:"]
    for table, count in sorted(_counts().items()):
        lines.append(f"  {table}: {count}")
    history_total = sum(
        model.objects.count()
        for app_label in ("accounts", "catalog", "activities", "entry")
        for model in apps.get_app_config(app_label).get_models()
        if model._meta.model_name.startswith("historical")
    )
    lines.append(f"  bảng lịch sử (tổng): {history_total}")
    return lines


def seed_demo(catalogs: Catalog) -> list[str]:
    before = _counts()
    lines = []

    periods = _ensure_periods()
    _seed_plans(catalogs)
    for spec in ACTIVITY_SPECS:
        activity = _ensure_activity(spec, catalogs)
        _seed_activity_phieu(activity, spec, catalogs)
    for spec in SUPPLEMENTAL_SPECS:
        _seed_supplemental(spec, catalogs)
    _seed_projects(catalogs)
    _seed_monthly(catalogs, periods)
    _seed_reports(catalogs)

    after = _counts()
    lines.append("Kết quả seed dữ liệu mẫu:")
    for table in sorted(after):
        lines.append(
            f"  {table}: {after[table]} (+{after[table] - before.get(table, 0)})"
        )
    lines.extend(_count_lines())
    return lines


@transaction.atomic
def seed_demo_atomic(catalogs: Catalog) -> list[str]:
    """Seed business rows atomically, then write report files outside the lock."""
    return seed_demo(catalogs)
