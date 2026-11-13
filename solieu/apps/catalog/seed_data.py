"""Idempotent rows for the HTKN, GDCN, and TTTK catalogs.

Annual plan rows are created once and never overwritten. The confirmed
HTKN-LOP plan from admin is not in this list, so a rerun leaves it alone.
"""

from decimal import Decimal

from django.core.management.base import CommandError
from django.db import transaction
from django.utils import timezone

from apps.catalog.models import (
    BieuMauChiTieu,
    CachTongHop,
    ChiTieu,
    ChiTieuKeHoach,
    CountSubject,
    DanhMucDoiTuong,
    KieuGhiNhan,
    LoaiHoatDong,
    LoaiHoTro,
    NguonSoLieu,
    NhomChiTieu,
    PhongBan,
    TrangThaiKeHoach,
)

DOI_TUONG = (
    "Sở ban ngành",
    "Viện/trường",
    "Doanh nghiệp",
    "Sinh viên/Học viên",
    "Cá nhân",
)
BON_NHOM = DOI_TUONG[:4]
HAI_NHOM = ("Viện/trường", "Doanh nghiệp")
NAM_NHOM = DOI_TUONG

NGUON = (
    "Tại sự kiện",
    "Phiếu khảo sát sau sự kiện",
    "techport.vn",
    "Phòng Thông tin – Thống kê",
    "Doanh nghiệp có công nghệ đăng ký",
    "Cá nhân, doanh nghiệp cung cấp",
    "Đơn vị tư vấn chiến lược",
    "Đối tác hợp tác",
    "Viện trường",
    "Cục Thông tin, Thống kê",
)
TAI_SU_KIEN = ("Tại sự kiện",)
SAU_SU_KIEN = ("Tại sự kiện", "Phiếu khảo sát sau sự kiện")

# phong, ten_mang, thu_tu, previous name to adopt when the new name is absent
GROUPS = (
    ("HTKN", "HTKN-HL", "Chương trình huấn luyện", 1, "Lớp huấn luyện"),
    ("HTKN", "HTKN-HN", "Hội nghị, hội thảo", 2, None),
    ("HTKN", "HTKN-TL", "Triển lãm", 3, None),
    ("HTKN", "HTKN-UOM", "Ươm tạo và tăng tốc", 4, None),
    ("HTKN", "HTKN-NGOAI", "Hỗ trợ dự án ngoài ngân sách NQ20", 5, None),
    ("HTKN", "HTKN-PS", "Nhiệm vụ phát sinh", 6, None),
    ("GDCN", "GDCN-SAN", "Sàn Techport", 1, None),
    ("GDCN", "GDCN-XT", "Xúc tiến chuyển giao công nghệ", 2, None),
    ("GDCN", "GDCN-KN", "Kết nối tư vấn chuyển giao công nghệ", 3, None),
    ("GDCN", "GDCN-VH", "Vận hành sàn", 4, None),
    ("TTTK", "TTTK-1", "Người dùng tin", 1, None),
    ("TTTK", "TTTK-2", "Thông tin hỗ trợ", 2, None),
    ("TTTK", "TTTK-3", "Sở hữu công nghiệp", 3, None),
    ("TTTK", "TTTK-4", "Chế độ báo cáo thống kê", 4, None),
    ("TTTK", "TTTK-5", "Điều tra thống kê", 5, None),
    ("TTTK", "TTTK-6", "Website thống kê", 6, None),
    ("TTTK", "TTTK-7", "Hội thảo phân tích xu hướng công nghệ", 7, None),
    ("TTTK", "TTTK-8", "Hệ thống liên kết nguồn lực thông tin", 8, None),
)

# Shared GDCN event results. One code, attached to every event form that can produce it.
_LIEN_KET = ("GDCN-MOU", "GDCN-BB", "GDCN-HD", "GDCN-GT")

# phong, ten_loai, co_ke_hoach_so_luong, form lines in thu_tu. Count indicators stay off the form.
LOAI = (
    (
        "HTKN",
        "Lớp huấn luyện",
        True,
        ("HTKN-LOP-HV", "HTKN-LOP-CN", "HTKN-LOP-CG", "HTKN-LOP-KS"),
    ),
    (
        "HTKN",
        "Hội nghị/hội thảo",
        True,
        ("HTKN-HN-ND", "HTKN-HN-CG"),
    ),
    (
        "HTKN",
        "Triển lãm",
        True,
        ("HTKN-TL-GH", "HTKN-TL-SP", "HTKN-TL-LQ", "HTKN-TL-CG", "HTKN-TL-KS"),
    ),
    ("HTKN", "Nhiệm vụ phát sinh", False, ()),
    (
        "GDCN",
        "Techmart",
        True,
        (
            "GDCN-TM-GH",
            "GDCN-TM-HT",
            "GDCN-TM-CG",
            "GDCN-TM-KH",
            "GDCN-TM-BB",
            *_LIEN_KET,
        ),
    ),
    (
        "GDCN",
        "Trình diễn công nghệ",
        True,
        (
            "GDCN-TD-CG",
            "GDCN-TD-DVTD",
            "GDCN-TD-DVTB",
            "GDCN-TD-CNTB",
            "GDCN-TD-KTT",
            "GDCN-TD-KTL",
            "GDCN-TD-LIVE",
            "GDCN-TD-HOTRO",
            "GDCN-TD-KHACH",
            "GDCN-YC-TRINH-DIEN",
            "GDCN-YC-KT",
            "GDCN-TD-TC",
            *_LIEN_KET,
        ),
    ),
    (
        "GDCN",
        "Sự kiện KH&CN tại tỉnh thành – trên toàn quốc",
        True,
        ("GDCN-TINH-DV", "GDCN-TINH-CNTB", *_LIEN_KET),
    ),
    (
        "GDCN",
        "Sự kiện KH&CN tại tỉnh thành – khu vực phía Nam",
        True,
        ("GDCN-TINH-DV", "GDCN-TINH-CNTB", *_LIEN_KET),
    ),
    (
        "GDCN",
        "Triển lãm Sàn GDCN tham gia",
        False,
        ("GDCN-TL-CNTB-DN", "GDCN-TL-KQ-VT", *_LIEN_KET),
    ),
    (
        "GDCN",
        "Cafe công nghệ",
        True,
        (
            "GDCN-CAFE-DV",
            "GDCN-CAFE-KTT",
            "GDCN-CAFE-KTL",
            "GDCN-CAFE-LIVE",
            "GDCN-MOU",
            "GDCN-YC-CAFE",
            "GDCN-BB",
            "GDCN-HD",
            "GDCN-GT",
            "GDCN-CAFE-TC",
        ),
    ),
    (
        "GDCN",
        "Hợp tác công nghệ",
        False,
        ("GDCN-HT-KQ", "GDCN-MOU", "GDCN-YC-CAFE", "GDCN-BB", "GDCN-HD", "GDCN-GT"),
    ),
    (
        "GDCN",
        "Kết nối ý tưởng",
        False,
        ("GDCN-KN-SP", "GDCN-MOU", "GDCN-YC-CAFE", "GDCN-BB", "GDCN-HD", "GDCN-GT"),
    ),
    (
        "TTTK",
        "Hội thảo xu hướng công nghệ",
        False,
        (
            "TTTK-HT-DK",
            "TTTK-HT-TT",
            "TTTK-HT-HL",
            "TTTK-HT-NHU-CAU",
            "TTTK-HT-CG",
        ),
    ),
)

# code, value, doi_tuong name or None. Create only. Empty plans are omitted.
PLANS = (
    ("GDCN-HS", "150", None),
    ("GDCN-TB", "500", None),
    ("GDCN-CG", "50", None),
    ("GDCN-TSTT", "20", None),
    ("GDCN-DVCU", "50", None),
    ("GDCN-LT", "200000", None),
    ("GDCN-YC-TECHPORT", "50", None),
    ("GDCN-BV", "128", None),
    ("GDCN-TM", "2", None),
    ("GDCN-TD", "9", None),
    ("GDCN-TINH-TQ", "10", None),
    ("GDCN-TINH-PN", "2", None),
    ("GDCN-TB-SAN", "100", None),
    ("GDCN-TD-HOTRO", "18", "Viện/trường"),
    ("GDCN-TD-HOTRO", "90", "Doanh nghiệp"),
    ("GDCN-TD-KHACH", "540", None),
    ("GDCN-TL-CNTB-DN", "90", None),
    ("GDCN-TL-KQ-VT", "17", None),
    ("GDCN-CAFE", "10", None),
    ("GDCN-HT-KQ", "5", None),
    ("GDCN-KN-SP", "15", None),
    ("GDCN-MOU", "30", None),
    ("GDCN-YC-CAFE", "25", None),
    ("GDCN-BB", "45", None),
    ("GDCN-HD", "50", None),
)


def _ct(ma, ten, don_vi, nhom, kieu, cach, **extra):
    row = {
        "ma": ma,
        "ten": ten,
        "don_vi": don_vi,
        "nhom": nhom,
        "kieu": kieu,
        "cach": cach,
        "parent": None,
        "loai": None,
        "count_subject": "",
        "loai_ho_tro": "",
        "linh_vuc": False,
        "doi_tuong": None,
        "nguon": None,
        "cap": None,
        "tu": None,
        "mau": None,
        "toi_thieu": None,
        "toi_da": None,
    }
    row.update(extra)
    return row


def _sum(ma, ten, don_vi, nhom, parent=None, **extra):
    return _ct(
        ma,
        ten,
        don_vi,
        nhom,
        KieuGhiNhan.ACTIVITY,
        CachTongHop.SUM,
        parent=parent,
        **extra,
    )


def _count(ma, ten, don_vi, nhom, loai):
    return _ct(
        ma,
        ten,
        don_vi,
        nhom,
        KieuGhiNhan.ACTIVITY,
        CachTongHop.COUNT,
        loai=loai,
        count_subject=CountSubject.ACTIVITY,
    )


def _month(ma, ten, don_vi, nhom, cach=CachTongHop.SUM, **extra):
    return _ct(ma, ten, don_vi, nhom, KieuGhiNhan.MONTH, cach, **extra)


def _project_count(ma, ten, nhom, loai_ho_tro):
    return _ct(
        ma,
        ten,
        "dự án",
        nhom,
        KieuGhiNhan.PROJECT,
        CachTongHop.COUNT,
        count_subject=CountSubject.PROJECT,
        loai_ho_tro=loai_ho_tro,
    )


INDICATORS = (
    _count("HTKN-LOP", "Số lớp huấn luyện", "lớp", "HTKN-HL", "Lớp huấn luyện"),
    _sum("HTKN-LOP-HV", "Số học viên tham gia", "người", "HTKN-HL", "HTKN-LOP"),
    _sum(
        "HTKN-LOP-CN",
        "Số học viên được cấp chứng nhận",
        "người",
        "HTKN-HL",
        "HTKN-LOP",
        cap="HTKN-LOP-HV",
    ),
    _sum(
        "HTKN-LOP-CG",
        "Số chuyên gia/giảng viên tham gia",
        "người",
        "HTKN-HL",
        "HTKN-LOP",
    ),
    _sum(
        "HTKN-LOP-KS",
        "Số học viên tham gia khảo sát",
        "người",
        "HTKN-HL",
        "HTKN-LOP",
        cap="HTKN-LOP-HV",
    ),
    _count("HTKN-HN", "Số hội nghị/hội thảo", "sự kiện", "HTKN-HN", "Hội nghị/hội thảo"),
    _sum("HTKN-HN-ND", "Số người tham dự", "người", "HTKN-HN", "HTKN-HN"),
    _sum("HTKN-HN-CG", "Số chuyên gia/diễn giả", "người", "HTKN-HN", "HTKN-HN"),
    _count("HTKN-TL", "Số triển lãm", "sự kiện", "HTKN-TL", "Triển lãm"),
    _sum("HTKN-TL-GH", "Số gian hàng", "gian hàng", "HTKN-TL", "HTKN-TL"),
    _sum(
        "HTKN-TL-SP",
        "Số sản phẩm/công nghệ/thiết bị trưng bày",
        "sản phẩm",
        "HTKN-TL",
        "HTKN-TL",
    ),
    _sum(
        "HTKN-TL-LQ",
        "Số lượt người tham quan/tham dự",
        "lượt",
        "HTKN-TL",
        "HTKN-TL",
    ),
    _sum("HTKN-TL-CG", "Số chuyên gia/diễn giả", "người", "HTKN-TL", "HTKN-TL"),
    _sum(
        "HTKN-TL-KS",
        "Số gian hàng tham gia khảo sát",
        "gian hàng",
        "HTKN-TL",
        "HTKN-TL",
        cap="HTKN-TL-GH",
    ),
    _project_count(
        "HTKN-DA-NC",
        "Số dự án được hỗ trợ ngày công lao động",
        "HTKN-UOM",
        LoaiHoTro.NGAY_CONG,
    ),
    _project_count(
        "HTKN-DA-CG",
        "Số dự án được hỗ trợ chuyên gia",
        "HTKN-UOM",
        LoaiHoTro.CHUYEN_GIA,
    ),
    _project_count(
        "HTKN-DA-DV",
        "Số dự án được hỗ trợ dịch vụ ươm tạo",
        "HTKN-UOM",
        LoaiHoTro.DICH_VU,
    ),
    _ct(
        "HTKN-DA-CG-SL",
        "Số chuyên gia đã kết nối với dự án",
        "người",
        "HTKN-UOM",
        KieuGhiNhan.PROJECT,
        CachTongHop.SUM,
    ),
    _project_count(
        "HTKN-DA-NGOAI",
        "Số dự án được hỗ trợ ngoài ngân sách NQ20",
        "HTKN-NGOAI",
        LoaiHoTro.KHAC,
    ),
    _month("GDCN-HS", "Hồ sơ công nghệ", "hồ sơ", "GDCN-SAN", nguon=TAI_SU_KIEN + ("Doanh nghiệp có công nghệ đăng ký",)),
    _month(
        "GDCN-TB",
        "Dây chuyền/thiết bị",
        "dây chuyền/thiết bị",
        "GDCN-SAN",
        nguon=TAI_SU_KIEN + ("Doanh nghiệp có công nghệ đăng ký",),
    ),
    _month(
        "GDCN-CG",
        "Chuyên gia tư vấn",
        "người",
        "GDCN-SAN",
        nguon=(
            "Tại sự kiện",
            "Đơn vị tư vấn chiến lược",
            "Đối tác hợp tác",
            "Viện trường",
        ),
    ),
    _month(
        "GDCN-TSTT",
        "Tài sản trí tuệ",
        "tài sản",
        "GDCN-SAN",
        nguon=("Phòng Thông tin – Thống kê", "Cá nhân, doanh nghiệp cung cấp"),
    ),
    _month(
        "GDCN-DVCU",
        "Đơn vị cung ứng",
        "đơn vị",
        "GDCN-SAN",
        doi_tuong=HAI_NHOM,
    ),
    _month("GDCN-LT", "Lượt truy cập", "lượt", "GDCN-SAN"),
    _month("GDCN-USER", "Người dùng (user) mới", "người", "GDCN-SAN", nguon=("techport.vn",)),
    _month(
        "GDCN-YC-TECHPORT",
        "Yêu cầu công nghệ qua techport.vn",
        "yêu cầu",
        "GDCN-SAN",
        nguon=("techport.vn",),
    ),
    _month("GDCN-KNCC", "Lượt kết nối cung – cầu", "lượt", "GDCN-SAN"),
    _month("GDCN-BV", "Bài viết truyền thông", "bài", "GDCN-SAN"),
    _month(
        "GDCN-TC-TT",
        "Lượt tiếp cận, tương tác qua truyền thông",
        "lượt",
        "GDCN-SAN",
    ),
    _month(
        "GDCN-TB-SAN",
        "Trưng bày CN&TB tại Sàn giao dịch công nghệ trực tiếp",
        "CN&TB",
        "GDCN-XT",
    ),
    _count("GDCN-TM", "Số sự kiện Techmart", "sự kiện", "GDCN-XT", "Techmart"),
    _sum("GDCN-TM-GH", "Số gian hàng", "gian hàng", "GDCN-XT", "GDCN-TM"),
    _sum("GDCN-TM-HT", "Số hội thảo", "hội thảo", "GDCN-XT", "GDCN-TM"),
    _sum("GDCN-TM-CG", "Số chuyên gia tư vấn", "người", "GDCN-XT", "GDCN-TM"),
    _sum("GDCN-TM-KH", "Số khách tham dự", "người", "GDCN-XT", "GDCN-TM"),
    _sum("GDCN-TM-BB", "Số biên bản tư vấn", "biên bản", "GDCN-XT", "GDCN-TM"),
    _count(
        "GDCN-TD",
        "Số sự kiện Trình diễn công nghệ",
        "sự kiện",
        "GDCN-XT",
        "Trình diễn công nghệ",
    ),
    _sum("GDCN-TD-CG", "Số chuyên gia báo cáo tham luận", "người", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-DVTD", "Số đơn vị trình diễn", "đơn vị", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-DVTB", "Số đơn vị trưng bày", "đơn vị", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-CNTB", "Số CN&TB giới thiệu", "CN&TB", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-KTT", "Số khách trực tiếp", "người", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-KTL", "Số khách trực tuyến", "người", "GDCN-XT", "GDCN-TD"),
    _sum("GDCN-TD-LIVE", "Số lượt xem livestream", "lượt", "GDCN-XT", "GDCN-TD"),
    _sum(
        "GDCN-TD-HOTRO",
        "Hỗ trợ lượt trưng bày công nghệ tại sự kiện",
        "CN&TB",
        "GDCN-XT",
        "GDCN-TD",
        doi_tuong=HAI_NHOM,
        nguon=SAU_SU_KIEN,
    ),
    _sum(
        "GDCN-TD-KHACH",
        "Tổng khách tham dự kết nối",
        "khách",
        "GDCN-XT",
        "GDCN-TD",
        nguon=SAU_SU_KIEN,
    ),
    _sum(
        "GDCN-YC-TRINH-DIEN",
        "Số yêu cầu công nghệ tại sự kiện Trình diễn công nghệ",
        "yêu cầu",
        "GDCN-XT",
        "GDCN-TD",
        nguon=SAU_SU_KIEN,
    ),
    _sum(
        "GDCN-YC-KT",
        "Số yêu cầu có khả năng hợp tác, triển khai",
        "yêu cầu",
        "GDCN-XT",
        "GDCN-TD",
        cap="GDCN-YC-TRINH-DIEN",
        nguon=SAU_SU_KIEN,
    ),
    _sum(
        "GDCN-TD-TC",
        "Lượt tiếp cận, tương tác qua sự kiện xúc tiến",
        "lượt",
        "GDCN-XT",
        "GDCN-TD",
    ),
    _count(
        "GDCN-TINH-TQ",
        "Số sự kiện KH&CN tại tỉnh thành – trên toàn quốc",
        "sự kiện",
        "GDCN-XT",
        "Sự kiện KH&CN tại tỉnh thành – trên toàn quốc",
    ),
    _count(
        "GDCN-TINH-PN",
        "Số sự kiện KH&CN tại tỉnh thành – khu vực phía Nam",
        "sự kiện",
        "GDCN-XT",
        "Sự kiện KH&CN tại tỉnh thành – khu vực phía Nam",
    ),
    _sum("GDCN-TINH-DV", "Số đơn vị tham gia", "đơn vị", "GDCN-XT"),
    _sum("GDCN-TINH-CNTB", "Số CN&TB giới thiệu", "CN&TB", "GDCN-XT"),
    _sum(
        "GDCN-TL-CNTB-DN",
        "Số CN&TB của doanh nghiệp được hỗ trợ tại triển lãm",
        "CN&TB",
        "GDCN-XT",
    ),
    _sum(
        "GDCN-TL-KQ-VT",
        "Số kết quả nghiên cứu của viện, trường được hỗ trợ tại triển lãm",
        "kết quả",
        "GDCN-XT",
    ),
    _count("GDCN-CAFE", "Số sự kiện Cafe công nghệ", "sự kiện", "GDCN-KN", "Cafe công nghệ"),
    _sum("GDCN-CAFE-DV", "Số đơn vị tham gia", "đơn vị", "GDCN-KN", "GDCN-CAFE"),
    _sum("GDCN-CAFE-KTT", "Số khách trực tiếp", "người", "GDCN-KN", "GDCN-CAFE"),
    _sum("GDCN-CAFE-KTL", "Số khách trực tuyến", "người", "GDCN-KN", "GDCN-CAFE"),
    _sum("GDCN-CAFE-LIVE", "Số lượt xem livestream", "lượt", "GDCN-KN", "GDCN-CAFE"),
    _sum(
        "GDCN-CAFE-TC",
        "Lượt tiếp cận, tương tác qua Cafe công nghệ",
        "lượt",
        "GDCN-KN",
        "GDCN-CAFE",
    ),
    _sum(
        "GDCN-HT-KQ",
        "Kết quả nghiên cứu của viện trường được hỗ trợ kết nối cung cầu",
        "kết quả",
        "GDCN-KN",
        nguon=TAI_SU_KIEN,
    ),
    _sum(
        "GDCN-KN-SP",
        "Sản phẩm KH&CN của doanh nghiệp được hỗ trợ kết nối cung cầu",
        "sản phẩm",
        "GDCN-KN",
        nguon=TAI_SU_KIEN,
    ),
    _sum("GDCN-MOU", "Biên bản ghi nhớ (MOU)", "biên bản", "GDCN-KN", nguon=TAI_SU_KIEN),
    _sum(
        "GDCN-YC-CAFE",
        "Số yêu cầu công nghệ tại Cafe công nghệ",
        "yêu cầu",
        "GDCN-KN",
        nguon=SAU_SU_KIEN,
    ),
    _sum(
        "GDCN-BB",
        "Số lượng kết nối (có biên bản)",
        "biên bản",
        "GDCN-KN",
        nguon=SAU_SU_KIEN,
    ),
    _sum("GDCN-HD", "Số hợp đồng sau kết nối", "hợp đồng", "GDCN-KN", nguon=TAI_SU_KIEN),
    _sum("GDCN-GT", "Tổng giá trị hợp đồng", "đồng", "GDCN-KN", nguon=TAI_SU_KIEN),
    _month(
        "GDCN-VH-TC",
        "Lượt tiếp cận, tương tác qua vận hành Sàn giao dịch công nghệ",
        "lượt",
        "GDCN-VH",
    ),
    _month(
        "TTTK-NDT",
        "Số người dùng tin đang phục vụ",
        "người",
        "TTTK-1",
        CachTongHop.CUMULATIVE,
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month(
        "TTTK-TIN-HT",
        "Số thông tin hỗ trợ cho người dùng",
        "tin",
        "TTTK-2",
        CachTongHop.CUMULATIVE,
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month(
        "TTTK-HD-SHCN",
        "Số hợp đồng mới",
        "hợp đồng",
        "TTTK-3",
        CachTongHop.CUMULATIVE,
    ),
    _month(
        "TTTK-DON-DK",
        "Số đơn đăng ký",
        "đơn",
        "TTTK-3",
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month(
        "TTTK-DON-CB",
        "Số đơn công bố",
        "đơn",
        "TTTK-3",
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month(
        "TTTK-TY-LE",
        "Tỷ lệ đơn công bố/đơn đã đăng ký",
        "tỷ lệ",
        "TTTK-3",
        CachTongHop.RATIO,
        tu="TTTK-DON-CB",
        mau="TTTK-DON-DK",
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month(
        "TTTK-DON-CAP",
        "Số đơn được cấp bằng bảo hộ sáng chế, nhãn hiệu",
        "đơn",
        "TTTK-3",
        CachTongHop.CUMULATIVE,
        doi_tuong=BON_NHOM,
        linh_vuc=True,
    ),
    _month("TTTK-BM", "Số biểu mẫu báo cáo", "biểu mẫu", "TTTK-4"),
    _month("TTTK-VB-BC", "Văn bản báo cáo kết quả", "văn bản", "TTTK-4"),
    _month("TTTK-PHIEU", "Số phiếu thu thập", "phiếu", "TTTK-5"),
    _month("TTTK-VB-DT", "Văn bản báo cáo kết quả điều tra", "văn bản", "TTTK-5"),
    _month("TTTK-RD-NHAN-LUC", "Tổng nhân lực R&D", "người", "TTTK-5", CachTongHop.LATEST),
    _month(
        "TTTK-RD-NHA-NC",
        "Tổng số nhà nghiên cứu",
        "người",
        "TTTK-5",
        CachTongHop.LATEST,
    ),
    _month("TTTK-RD-CHI", "Tổng chi cho R&D", "đồng", "TTTK-5", CachTongHop.LATEST),
    _month("TTTK-RD-NV", "Số nhiệm vụ KH&CN", "nhiệm vụ", "TTTK-5", CachTongHop.LATEST),
    _month(
        "TTTK-WEB-LUOT",
        "Số lượt truy cập website thống kê",
        "lượt",
        "TTTK-6",
        CachTongHop.CUMULATIVE,
    ),
    _month(
        "TTTK-WEB-ND",
        "Số lượt người dùng website thống kê",
        "lượt",
        "TTTK-6",
        CachTongHop.CUMULATIVE,
    ),
    _sum("TTTK-HT-DK", "Số khách đăng ký", "người", "TTTK-7"),
    _sum("TTTK-HT-TT", "Số khách tham dự thực tế", "người", "TTTK-7", doi_tuong=NAM_NHOM),
    _ct(
        "TTTK-HT-HL",
        "Mức độ hài lòng",
        "điểm",
        "TTTK-7",
        KieuGhiNhan.ACTIVITY,
        CachTongHop.AVERAGE,
        doi_tuong=NAM_NHOM,
        linh_vuc=True,
        toi_thieu=Decimal("1"),
        toi_da=Decimal("5"),
    ),
    _sum(
        "TTTK-HT-NHU-CAU",
        "Nhu cầu tiếp cận và sử dụng thông tin",
        "người",
        "TTTK-7",
        doi_tuong=NAM_NHOM,
        linh_vuc=True,
    ),
    _sum("TTTK-HT-CG", "Nhu cầu kết nối chuyên gia", "nhu cầu", "TTTK-7"),
    _month("TTTK-HT-TC", "Số lượt truy cập báo cáo toàn cảnh", "lượt", "TTTK-7"),
    _month(
        "TTTK-LK-DV",
        "Số đơn vị/thành viên kết nối",
        "đơn vị",
        "TTTK-8",
        CachTongHop.CUMULATIVE,
    ),
    _month(
        "TTTK-LK-TL",
        "Số tài liệu KH&CN do đơn vị thành viên đóng góp",
        "tài liệu",
        "TTTK-8",
        CachTongHop.CUMULATIVE,
    ),
    _month(
        "TTTK-LK-LUOT",
        "Số lượt truy cập hệ thống liên kết",
        "lượt",
        "TTTK-8",
        CachTongHop.CUMULATIVE,
    ),
)


class _Tally:
    _RANK = {"kept": 0, "updated": 1, "created": 2}
    _FAMILIES = (
        "doi_tuong",
        "nguon",
        "nhom",
        "loai_hoat_dong",
        "chi_tieu",
        "bieu_mau",
        "ke_hoach",
    )

    def __init__(self):
        self._rows = {}

    def mark(self, family, key, status):
        token = (family, key)
        current = self._rows.get(token)
        if current is None or self._RANK[status] > self._RANK[current]:
            self._rows[token] = status

    def lines(self):
        output = []
        for family in self._FAMILIES:
            counts = {"created": 0, "updated": 0, "kept": 0}
            for (name, _key), status in self._rows.items():
                if name == family:
                    counts[status] += 1
            output.append(
                f"{family}: created={counts['created']} "
                f"updated={counts['updated']} kept={counts['kept']}"
            )
        return output


def _check_specs():
    codes = [row["ma"] for row in INDICATORS]
    if len(codes) != len(set(codes)):
        raise CommandError("Mã chỉ tiêu trong seed bị trùng.")
    known = set(codes)
    group_keys = {row[1] for row in GROUPS}
    loai_names = {(row[0], row[1]) for row in LOAI}
    for row in INDICATORS:
        if row["nhom"] not in group_keys:
            raise CommandError(f"Chỉ tiêu {row['ma']} chưa có mảng {row['nhom']}.")
        phong = row["nhom"].split("-", 1)[0]
        if row["loai"] and (phong, row["loai"]) not in loai_names:
            raise CommandError(f"Chỉ tiêu {row['ma']} chưa có loại {row['loai']}.")
        for link in ("parent", "cap", "tu", "mau"):
            if row[link] and row[link] not in known:
                raise CommandError(f"Chỉ tiêu {row['ma']} trỏ tới mã không có.")
        if row["parent"]:
            parent = next(item for item in INDICATORS if item["ma"] == row["parent"])
            if parent["nhom"] != row["nhom"]:
                raise CommandError(f"Chỉ tiêu {row['ma']} khác mảng với chỉ tiêu cha.")
        if row["cach"] == CachTongHop.RATIO and not (row["tu"] and row["mau"]):
            raise CommandError(f"Chỉ tiêu tỷ lệ {row['ma']} thiếu tử số hoặc mẫu số.")
        if row["cach"] == CachTongHop.COUNT and row["count_subject"] == CountSubject.ACTIVITY:
            if not row["loai"]:
                raise CommandError(f"Chỉ tiêu đếm {row['ma']} chưa gắn loại hoạt động.")
        if row["count_subject"] == CountSubject.PROJECT and not row["loai_ho_tro"]:
            raise CommandError(f"Chỉ tiêu đếm dự án {row['ma']} chưa có loại hỗ trợ.")
    for phong, ten, _flag, lines in LOAI:
        for code in lines:
            if code not in known:
                raise CommandError(f"Biểu mẫu {ten} thiếu chỉ tiêu {code}.")
            spec = next(item for item in INDICATORS if item["ma"] == code)
            if spec["loai"] == ten:
                raise CommandError(f"Chỉ tiêu đếm {code} không được nằm trong biểu mẫu.")
            if not spec["nhom"].startswith(phong):
                raise CommandError(f"Biểu mẫu {ten} gắn chỉ tiêu khác phòng {code}.")
    for code, _value, doi_ten in PLANS:
        if code not in known:
            raise CommandError(f"Kế hoạch trỏ tới mã không có: {code}.")
        if doi_ten and doi_ten not in DOI_TUONG:
            raise CommandError(f"Kế hoạch {code} dùng đối tượng lạ.")


def _apply(obj, values):
    changed = False
    for name, value in values.items():
        if getattr(obj, name) != value:
            setattr(obj, name, value)
            changed = True
    return changed


def _ensure(model, lookup, values):
    row = model.objects.filter(**lookup).first()
    created = row is None
    if created:
        row = model(**lookup)
    changed = _apply(row, values)
    if created or changed:
        row.save()
    return row, created, changed or created


def _mark(stats, family, key, created, changed):
    if created:
        stats.mark(family, key, "created")
    elif changed:
        stats.mark(family, key, "updated")
    else:
        stats.mark(family, key, "kept")


def _set_m2m(row, field, targets):
    if targets is None:
        return False
    desired = {item.pk for item in targets}
    current = set(getattr(row, field).values_list("pk", flat=True))
    if current == desired:
        return False
    getattr(row, field).set(desired)
    return True


def _named(model, field, names, family, stats):
    found = {}
    for name in names:
        row, created, changed = _ensure(model, {field: name}, {})
        _mark(stats, family, name, created, changed)
        found[name] = row
    return found


def _groups(phong, stats):
    found = {}
    for ma_phong, key, ten_mang, thu_tu, rename_from in GROUPS:
        department = phong[ma_phong]
        row = NhomChiTieu.objects.filter(phong=department, ten_mang=ten_mang).first()
        created = False
        if row is None and rename_from:
            row = NhomChiTieu.objects.filter(
                phong=department, ten_mang=rename_from
            ).first()
        if row is None:
            row = NhomChiTieu(phong=department, ten_mang=ten_mang, thu_tu=thu_tu)
            row.save()
            created = True
            changed = True
        else:
            changed = _apply(row, {"ten_mang": ten_mang, "thu_tu": thu_tu})
            if changed:
                row.save()
        _mark(stats, "nhom", key, created, changed)
        found[key] = row
    return found


def _activity_types(phong, stats):
    found = {}
    for ma_phong, ten_loai, co_so_luong, _lines in LOAI:
        row, created, changed = _ensure(
            LoaiHoatDong,
            {"phong": phong[ma_phong], "ten_loai": ten_loai},
            {"co_ke_hoach_so_luong": co_so_luong},
        )
        _mark(stats, "loai_hoat_dong", (ma_phong, ten_loai), created, changed)
        found[(ma_phong, ten_loai)] = row
    return found


def _scalar(spec, groups, activity_types):
    phong = spec["nhom"].split("-", 1)[0]
    loai = activity_types.get((phong, spec["loai"])) if spec["loai"] else None
    return {
        "ten_chi_tieu": spec["ten"],
        "don_vi_tinh": spec["don_vi"],
        "nhom_id": groups[spec["nhom"]].pk,
        "kieu_ghi_nhan": spec["kieu"],
        "cach_tong_hop": spec["cach"],
        "count_subject": spec["count_subject"],
        "loai_ho_tro": spec["loai_ho_tro"],
        "loai_hoat_dong_id": None if loai is None else loai.pk,
        "phan_loai_doi_tuong": spec["doi_tuong"] is not None,
        "phan_loai_linh_vuc": spec["linh_vuc"],
        "gia_tri_toi_thieu": spec["toi_thieu"],
        "gia_tri_toi_da": spec["toi_da"],
        "dang_su_dung": True,
    }


def _link_ids(spec, by_code):
    def pk(code):
        return None if not code else by_code[code].pk

    return {
        "chi_tieu_cha_id": pk(spec["parent"]),
        "khong_vuot_chi_tieu_id": pk(spec["cap"]),
        "chi_tieu_tu_so_id": pk(spec["tu"]),
        "chi_tieu_mau_so_id": pk(spec["mau"]),
    }


def _indicators(groups, activity_types, stats):
    by_code = {}
    for spec in INDICATORS:
        if spec["cach"] == CachTongHop.RATIO:
            continue
        row, created, changed = _ensure(
            ChiTieu,
            {"ma_chi_tieu": spec["ma"]},
            _scalar(spec, groups, activity_types),
        )
        _mark(stats, "chi_tieu", spec["ma"], created, changed)
        by_code[spec["ma"]] = row
    for spec in INDICATORS:
        if spec["cach"] == CachTongHop.RATIO:
            values = _scalar(spec, groups, activity_types)
            values.update(_link_ids(spec, by_code))
            row, created, changed = _ensure(
                ChiTieu, {"ma_chi_tieu": spec["ma"]}, values
            )
            _mark(stats, "chi_tieu", spec["ma"], created, changed)
            by_code[spec["ma"]] = row
            continue
        row = by_code[spec["ma"]]
        if _apply(row, _link_ids(spec, by_code)):
            row.save()
            stats.mark("chi_tieu", spec["ma"], "updated")
    return by_code


def _relations(by_code, nguon, doi_tuong, stats):
    for spec in INDICATORS:
        row = by_code[spec["ma"]]
        sources = None if spec["nguon"] is None else [nguon[name] for name in spec["nguon"]]
        objects = (
            None
            if spec["doi_tuong"] is None
            else [doi_tuong[name] for name in spec["doi_tuong"]]
        )
        changed = _set_m2m(row, "nguon_cho_phep", sources)
        changed = _set_m2m(row, "doi_tuong_ap_dung", objects) or changed
        if changed:
            row.save()
            stats.mark("chi_tieu", spec["ma"], "updated")


def _forms(activity_types, by_code, stats):
    for ma_phong, ten_loai, _flag, lines in LOAI:
        loai = activity_types[(ma_phong, ten_loai)]
        for thu_tu, code in enumerate(lines, start=1):
            _row, created, changed = _ensure(
                BieuMauChiTieu,
                {"loai_hoat_dong": loai, "chi_tieu": by_code[code]},
                {"bat_buoc": True, "thu_tu": thu_tu},
            )
            _mark(stats, "bieu_mau", (loai.pk, code), created, changed)


def _plans(by_code, doi_tuong, stats):
    nam = timezone.localdate().year
    for code, value, doi_ten in PLANS:
        subject = None if doi_ten is None else doi_tuong[doi_ten]
        key = (code, nam, None if subject is None else subject.pk)
        existing = ChiTieuKeHoach.objects.filter(
            chi_tieu=by_code[code],
            nam=nam,
            doi_tuong=subject,
        ).first()
        if existing is not None:
            stats.mark("ke_hoach", key, "kept")
            continue
        ChiTieuKeHoach(
            chi_tieu=by_code[code],
            nam=nam,
            doi_tuong=subject,
            gia_tri_ke_hoach=Decimal(value),
            trang_thai=TrangThaiKeHoach.DU_THAO,
        ).save()
        stats.mark("ke_hoach", key, "created")


@transaction.atomic
def seed_catalog():
    _check_specs()
    phong = {
        row.ma_phong: row
        for row in PhongBan.objects.filter(ma_phong__in=("HTKN", "GDCN", "TTTK"))
    }
    missing = [ma for ma in ("HTKN", "GDCN", "TTTK") if ma not in phong]
    if missing:
        raise CommandError(
            "Chưa có phòng: " + ", ".join(missing) + ". Chạy seed_localhost trước."
        )
    stats = _Tally()
    doi_tuong = _named(DanhMucDoiTuong, "ten_doi_tuong", DOI_TUONG, "doi_tuong", stats)
    nguon = _named(NguonSoLieu, "ten_nguon", NGUON, "nguon", stats)
    groups = _groups(phong, stats)
    activity_types = _activity_types(phong, stats)
    by_code = _indicators(groups, activity_types, stats)
    _relations(by_code, nguon, doi_tuong, stats)
    _forms(activity_types, by_code, stats)
    _plans(by_code, doi_tuong, stats)
    return stats.lines()
