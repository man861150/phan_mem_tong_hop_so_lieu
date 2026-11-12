"""Aggregation, Excel export, Word export, and published reports."""

from __future__ import annotations

import os
import tempfile
from datetime import date
from decimal import Decimal
from io import BytesIO, StringIO
from pathlib import Path
from zipfile import ZipFile

from django.conf import settings
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management import call_command
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from docx import Document
from openpyxl import load_workbook

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import DuAn, HoatDong, TrangThaiHoatDong
from apps.catalog.models import (
    ChiTieu,
    ChiTieuKeHoach,
    DanhMucDoiTuong,
    DanhMucLinhVuc,
    KyBaoCao,
    TrangThaiKeHoach,
    TrangThaiKy,
)
from apps.entry.models import (
    HoTroDuAn,
    LoaiPhieu,
    PhieuNhapLieu,
    SoLieu,
    TrangThaiPhieu,
)
from apps.reporting.formatting import format_vi_number
from apps.reporting.models import BaoCaoDaXuat, BaoCaoDaXuatDong
from apps.reporting.periods import (
    months_in_period,
    period_label,
    period_slug,
    resolve_period,
    today,
)
from apps.reporting.rollup import ReportPeriod, rollup


class ReportFixtureMixin:
    @classmethod
    def setUpTestData(cls):
        from apps.catalog.models import PhongBan

        cls.htkn = PhongBan.objects.create(
            ma_phong="HTKN",
            ten_phong="Phòng HTKN",
        )
        cls.gdcn = PhongBan.objects.create(
            ma_phong="GDCN",
            ten_phong="Phòng Giao dịch công nghệ",
        )
        cls.tttk = PhongBan.objects.create(
            ma_phong="TTTK",
            ten_phong="Phòng Thông tin – Thống kê",
        )
        cls.bgd = PhongBan.objects.create(
            ma_phong="BGĐ",
            ten_phong="Ban Giám đốc",
        )
        call_command("seed_catalog", verbosity=0, stdout=StringIO())

        cls.cb_htkn = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Cán bộ HTKN",
            role=Role.ENTRY_OFFICER,
            phong=cls.htkn,
            password="test-pass-1",
        )
        cls.ld_htkn = User.objects.create_user(
            username="ld.htkn",
            ho_ten="Lãnh đạo HTKN",
            role=Role.DEPARTMENT_HEAD,
            phong=cls.htkn,
            password="test-pass-1",
        )
        cls.cb_tttk = User.objects.create_user(
            username="cb.tttk",
            ho_ten="Cán bộ TTTK",
            role=Role.ENTRY_OFFICER,
            phong=cls.tttk,
            password="test-pass-1",
        )
        cls.ld_tt = User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo Trung tâm",
            role=Role.CENTER_HEAD,
            phong=cls.bgd,
            password="test-pass-1",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị hệ thống",
            role=Role.SYSTEM_ADMIN,
            is_staff=True,
            password="test-pass-1",
        )

        cls.year = today().year
        cls.month = today().month
        cls.ky = KyBaoCao.objects.create(
            nam=cls.year,
            so_ky=cls.month,
            trang_thai=TrangThaiKy.MO,
        )

        cls.chi_tieu_hv = ChiTieu.objects.get(ma_chi_tieu="HTKN-LOP-HV")
        cls.chi_tieu_lop = ChiTieu.objects.get(ma_chi_tieu="HTKN-LOP")
        cls.chi_tieu_hs = ChiTieu.objects.get(ma_chi_tieu="GDCN-HS")
        cls.chi_tieu_ndt = ChiTieu.objects.get(ma_chi_tieu="TTTK-NDT")
        cls.chi_tieu_hn = ChiTieu.objects.get(ma_chi_tieu="HTKN-HN")
        cls._confirm_plan(cls.chi_tieu_hv, "100")
        cls._confirm_plan(cls.chi_tieu_hs, "150")
        cls._confirm_plan(cls.chi_tieu_ndt, "200")

        from apps.catalog.models import LoaiHoatDong

        cls.loai_lop = LoaiHoatDong.objects.get(
            phong=cls.htkn,
            ten_loai="Lớp huấn luyện",
        )
        cls.loai_hn = LoaiHoatDong.objects.get(
            phong=cls.htkn,
            ten_loai="Hội nghị/hội thảo",
        )

        class_date = date(cls.year, cls.month, 5)
        cls.activity = HoatDong.objects.create(
            loai_hoat_dong=cls.loai_lop,
            ten="Lớp khởi nghiệp tháng này",
            tu_ngay=class_date,
            den_ngay=class_date,
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        cls.activity_phieu = PhieuNhapLieu.objects.create(
            phong=cls.htkn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=cls.activity,
            nguoi_nhap=cls.cb_htkn,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        SoLieu.objects.create(
            phieu=cls.activity_phieu,
            chi_tieu=cls.chi_tieu_hv,
            gia_tri=Decimal("25"),
        )

        cls.gap_activity = HoatDong.objects.create(
            loai_hoat_dong=cls.loai_hn,
            ten="Hội nghị chưa có phiếu",
            tu_ngay=date(cls.year, cls.month, 6),
            den_ngay=date(cls.year, cls.month, 6),
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )

        cls.pending_month = PhieuNhapLieu.objects.create(
            phong=cls.htkn,
            loai_phieu=LoaiPhieu.THANG,
            ky=cls.ky,
            nguoi_nhap=cls.cb_htkn,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )

        cls.tttk_phieu = PhieuNhapLieu.objects.create(
            phong=cls.tttk,
            loai_phieu=LoaiPhieu.THANG,
            ky=cls.ky,
            nguoi_nhap=cls.cb_tttk,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        doanh_nghiep = DanhMucDoiTuong.objects.get(ten_doi_tuong="Doanh nghiệp")
        sinh_vien = DanhMucDoiTuong.objects.get(
            ten_doi_tuong="Sinh viên/Học viên"
        )
        linh_vuc = DanhMucLinhVuc.objects.create(
            he_thong="qd36",
            ma="QD36-01",
            ten="Công nghệ thông tin",
            cap=1,
        )
        SoLieu.objects.create(
            phieu=cls.tttk_phieu,
            chi_tieu=cls.chi_tieu_ndt,
            gia_tri=Decimal("100"),
        )
        SoLieu.objects.create(
            phieu=cls.tttk_phieu,
            chi_tieu=cls.chi_tieu_ndt,
            doi_tuong=doanh_nghiep,
            gia_tri=Decimal("60"),
        )
        SoLieu.objects.create(
            phieu=cls.tttk_phieu,
            chi_tieu=cls.chi_tieu_ndt,
            doi_tuong=sinh_vien,
            gia_tri=Decimal("40"),
        )
        SoLieu.objects.create(
            phieu=cls.tttk_phieu,
            chi_tieu=cls.chi_tieu_ndt,
            linh_vuc=linh_vuc,
            gia_tri=Decimal("100"),
        )

        cls.gdcn_phieu = PhieuNhapLieu.objects.create(
            phong=cls.gdcn,
            loai_phieu=LoaiPhieu.THANG,
            ky=cls.ky,
            nguoi_nhap=cls.cb_htkn,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        SoLieu.objects.create(
            phieu=cls.gdcn_phieu,
            chi_tieu=cls.chi_tieu_hs,
            gia_tri=Decimal("20"),
        )

    @classmethod
    def _confirm_plan(cls, chi_tieu, value):
        plan = ChiTieuKeHoach.objects.filter(
            chi_tieu=chi_tieu,
            nam=cls.year,
            doi_tuong__isnull=True,
        ).first()
        if plan is None:
            plan = ChiTieuKeHoach(
                chi_tieu=chi_tieu,
                nam=cls.year,
                gia_tri_ke_hoach=Decimal(value),
                trang_thai=TrangThaiKeHoach.DA_XAC_NHAN,
            )
        else:
            plan.gia_tri_ke_hoach = Decimal(value)
            plan.trang_thai = TrangThaiKeHoach.DA_XAC_NHAN
        plan.save()

    def login(self, user):
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        return client

    def response_bytes(self, response):
        if hasattr(response, "streaming_content"):
            return b"".join(response.streaming_content)
        return response.content

    def month_query(self, **overrides):
        values = {
            "kind": "month",
            "year": self.year,
            "month": self.month,
        }
        values.update(overrides)
        return values


class FormattingAndPeriodTests(TestCase):
    def test_vietnamese_number_format(self):
        self.assertEqual(format_vi_number(1234), "1.234")
        self.assertEqual(format_vi_number(Decimal("1200.5")), "1.200,5")
        self.assertEqual(format_vi_number(Decimal("1200.50")), "1.200,5")
        self.assertEqual(format_vi_number(Decimal("-1200.5")), "-1.200,5")
        self.assertEqual(format_vi_number(None), "—")

    def test_word_templates_have_the_expected_placeholders(self):
        template_dir = Path(settings.BASE_DIR) / "report_templates"
        expected = {
            "htkn.docx": ("{%tr for row in rows %}", "danh_sach"),
            "gdcn.docx": ("{%tr for row in rows %}",),
            "tttk.docx": ("{%tr for row in rows %}", "row.danh_gia"),
            "trung_tam.docx": ("phong.rows", "departments", "row.danh_gia"),
        }
        for name, markers in expected.items():
            document_xml = (
                ZipFile(template_dir / name)
                .read("word/document.xml")
                .decode()
            )
            for marker in markers:
                self.assertIn(marker, document_xml)

    def test_period_helpers(self):
        period = resolve_period("month", 2026, month=11)
        self.assertEqual(period_label(period), "Tháng 11/2026")
        self.assertEqual(period_slug(period), "thang-11-2026")
        quarter = resolve_period("quarter", 2026, quarter=4)
        self.assertEqual(period_label(quarter), "Quý 4/2026")
        self.assertEqual(len(months_in_period(quarter)), 3)
        annual = resolve_period("year", 2026)
        self.assertEqual(period_label(annual), "Năm 2026")
        self.assertEqual(len(months_in_period(annual)), 12)


class PreviewTests(ReportFixtureMixin, TestCase):
    def test_entry_officer_sees_approved_class_and_no_picker(self):
        client = self.login(self.cb_htkn)
        response = client.get(reverse("reporting:bao_cao"), self.month_query())
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Số lớp huấn luyện", content)
        self.assertIn("Số học viên tham gia", content)
        self.assertIn("25", content)
        self.assertNotIn('<select name="phong"', content)
        self.assertIn("Phòng HTKN", content)

    def test_department_head_sees_same_department(self):
        client = self.login(self.ld_htkn)
        response = client.get(reverse("reporting:bao_cao"), self.month_query())
        self.assertEqual(response.status_code, 200)
        self.assertIn("Số lớp huấn luyện", response.content.decode())

    def test_cross_department_request_is_forbidden(self):
        client = self.login(self.cb_htkn)
        response = client.get(
            reverse("reporting:bao_cao"),
            self.month_query(phong=self.tttk.pk),
        )
        self.assertEqual(response.status_code, 403)

    def test_center_scope_stacks_three_departments(self):
        client = self.login(self.ld_tt)
        response = client.get(
            reverse("reporting:bao_cao"),
            {"kind": "month", "year": self.year, "month": self.month},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("PHÒNG GDCN", content)
        self.assertIn("PHÒNG TTTK", content)
        self.assertIn("PHÒNG HTKN", content)
        self.assertLess(content.index("PHÒNG GDCN"), content.index("PHÒNG TTTK"))
        self.assertLess(content.index("PHÒNG TTTK"), content.index("PHÒNG HTKN"))

    def test_period_requires_month(self):
        client = self.login(self.cb_htkn)
        response = client.get(
            reverse("reporting:bao_cao"),
            {"kind": "month", "year": self.year},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("Vui lòng chọn tháng.", response.content.decode())

    def test_gap_warning_and_accepted_note(self):
        client = self.login(self.cb_htkn)
        query = {"kind": "quarter", "year": self.year, "quarter": 4}
        response = client.get(reverse("reporting:bao_cao"), query)
        self.assertIn("Hội nghị chưa có phiếu", response.content.decode())
        self.assertIn("Vẫn lập báo cáo", response.content.decode())
        query["tiep_tuc"] = "1"
        response = client.get(reverse("reporting:bao_cao"), query)
        self.assertIn("Số liệu chưa đầy đủ", response.content.decode())

    def test_tttk_breakdown_and_htkn_activity_list(self):
        client = self.login(self.ld_tt)
        tttk = client.get(
            reverse("reporting:bao_cao"),
            self.month_query(phong=self.tttk.pk),
        )
        text = tttk.content.decode()
        self.assertIn("Phân tích theo đối tượng và lĩnh vực", text)
        self.assertIn("Doanh nghiệp", text)
        self.assertIn("QD36-01", text)
        htkn = client.get(
            reverse("reporting:bao_cao"),
            self.month_query(phong=self.htkn.pk),
        )
        self.assertIn("Lớp khởi nghiệp tháng này", htkn.content.decode())

    def test_effectiveness_note_survives_refresh(self):
        client = self.login(self.cb_tttk)
        note = "Hiệu quả tốt trong tháng"
        post = {
            **self.month_query(phong=self.tttk.pk),
            f"danh_gia_{self.tttk.pk}_{self.chi_tieu_ndt.pk}": note,
        }
        response = client.post(reverse("reporting:bao_cao"), post, follow=True)
        self.assertEqual(response.status_code, 200)
        self.assertIn(note, response.content.decode())
        refreshed = client.get(
            reverse("reporting:bao_cao"),
            self.month_query(phong=self.tttk.pk),
        )
        self.assertIn(note, refreshed.content.decode())

    def test_rollup_is_the_source_for_class_row(self):
        period = ReportPeriod.month(self.year, self.month)
        rows = rollup(period, department_id=self.htkn.pk)
        row = next(item for item in rows if item.ma_chi_tieu == "HTKN-LOP-HV")
        self.assertEqual(row.period_value, Decimal("25"))
        self.assertEqual(row.plan, Decimal("100"))


class DashboardTests(ReportFixtureMixin, TestCase):
    def test_home_requires_login(self):
        response = Client(HTTP_HOST="localhost").get(reverse("home"))
        self.assertEqual(response.status_code, 302)
        self.assertIn(reverse("accounts:login"), response["Location"])

    def test_entry_home_lists_only_own_drafts_and_returns(self):
        draft = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.NHAP,
        )
        returned = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.TRA_LAI,
        )
        other_draft = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
            nguoi_nhap=self.ld_htkn,
            trang_thai=TrangThaiPhieu.NHAP,
        )
        response = self.login(self.cb_htkn).get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(
            reverse("entry:phieu_detail", args=[draft.pk]),
            content,
        )
        self.assertIn(
            reverse("entry:phieu_detail", args=[returned.pk]),
            content,
        )
        self.assertNotIn(
            reverse("entry:phieu_detail", args=[other_draft.pk]),
            content,
        )
        self.assertIn("Phiếu nháp của tôi", content)
        self.assertIn("Phiếu bị trả lại", content)
        self.assertNotIn("Phiếu chờ duyệt", content)
        self.assertNotIn("/duyet/", content)

    def test_department_head_sees_pending_count_and_queue_link(self):
        response = self.login(self.ld_htkn).get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Phiếu chờ duyệt", content)
        self.assertIn(">1<", content)
        self.assertIn(reverse("entry:duyet_list"), content)

    def test_center_home_is_read_only_and_has_department_cards(self):
        response = self.login(self.ld_tt).get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Phiếu nháp của tôi", content)
        self.assertNotIn("/phieu/", content)
        self.assertNotIn("/duyet/", content)
        self.assertIn("GDCN", content)
        self.assertIn("TTTK", content)
        self.assertIn("HTKN", content)
        self.assertEqual(
            response.context["selected_department"].ma_phong,
            "HTKN",
        )

    def test_system_admin_sees_same_read_only_dashboard(self):
        response = self.login(self.admin).get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertNotIn("Phiếu nháp của tôi", content)
        self.assertNotIn("/phieu/", content)
        self.assertNotIn("/duyet/", content)

    def test_home_initializes_exactly_two_charts(self):
        response = self.login(self.ld_tt).get(reverse("home"))
        content = response.content.decode()
        self.assertEqual(content.count("echarts.init"), 2)
        self.assertIn('id="chart1-data"', content)
        self.assertIn('id="chart2-data"', content)

    def test_percent_chart_uses_average_and_omits_only_track(self):
        response = self.login(self.ld_tt).get(reverse("home"))
        chart = response.context["chart1"]
        htkn_index = chart["labels"].index("HTKN")
        self.assertEqual(chart["values"][htkn_index], 25.0)

        scoped = self.login(self.cb_htkn).get(reverse("home"))
        chart = scoped.context["chart1"]
        self.assertEqual(chart["labels"], ["Chương trình huấn luyện"])
        self.assertEqual(chart["values"], [25.0])
        cards = scoped.context["completion_cards"]
        self.assertEqual([card["ma_phong"] for card in cards], ["HTKN"])

    def test_chart2_endpoint_switches_department_and_respects_scope(self):
        center = self.login(self.ld_tt)
        response = center.get(
            reverse("home"),
            {"chart": "2", "phong": self.tttk.pk},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/json")
        payload = response.json()
        self.assertIn("Số người dùng tin đang phục vụ", payload["labels"])
        self.assertNotIn("Số học viên tham gia", payload["labels"])

        forbidden = self.login(self.cb_htkn).get(
            reverse("home"),
            {"chart": "2", "phong": self.tttk.pk},
        )
        self.assertEqual(forbidden.status_code, 403)


class ProgressTableTests(ReportFixtureMixin, TestCase):
    def progress_row(self, response, ma_chi_tieu):
        for block in response.context["department_blocks"]:
            for group in block["groups"]:
                for row in group["rows"]:
                    if row["ma_chi_tieu"] == ma_chi_tieu:
                        return row
        return None

    def test_entry_officer_sees_only_own_department(self):
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do"),
            {"year": self.year},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("PHÒNG HTKN", content)
        self.assertNotIn("PHÒNG GDCN", content)
        self.assertNotIn("PHÒNG TTTK", content)
        self.assertIn("25%", content)
        self.assertIn("Chậm tiến độ", content)

    def test_center_sees_all_reporting_departments(self):
        response = self.login(self.ld_tt).get(
            reverse("reporting:tien_do"),
            {"year": self.year},
        )
        content = response.content.decode()
        self.assertIn("PHÒNG GDCN", content)
        self.assertIn("PHÒNG TTTK", content)
        self.assertIn("PHÒNG HTKN", content)
        self.assertLess(content.index("PHÒNG GDCN"), content.index("PHÒNG HTKN"))

    def test_only_track_row_shows_cumulative_and_dash_percent(self):
        response = self.login(self.ld_tt).get(
            reverse("reporting:tien_do"),
            {"year": self.year, "phong": self.htkn.pk},
        )
        row = self.progress_row(response, "HTKN-LOP")
        self.assertIsNotNone(row)
        self.assertTrue(row["only_track"])
        self.assertTrue(row["percent_missing"])
        self.assertEqual(row["cumulative"], "1")
        self.assertEqual(row["percent"], "—")
        self.assertIn("Chỉ theo dõi", response.content.decode())

    def test_cross_department_filter_is_forbidden(self):
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do"),
            {"year": self.year, "phong": self.tttk.pk},
        )
        self.assertEqual(response.status_code, 403)

    def test_invalid_year_falls_back_to_current_year(self):
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do"),
            {"year": "not-a-year"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.context["year"], today().year)
        self.assertIn("Năm không hợp lệ", response.content.decode())

    def test_progress_page_has_no_chart_initialization(self):
        response = self.login(self.ld_tt).get(
            reverse("reporting:tien_do"),
            {"year": self.year},
        )
        content = response.content.decode()
        self.assertEqual(content.count("echarts.init"), 0)
        self.assertNotIn('id="chart1"', content)
        self.assertNotIn('id="chart2"', content)

    def test_pending_toggle_keeps_official_cumulative(self):
        pending = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.THANG,
            ky=self.ky,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )
        SoLieu.objects.create(
            phieu=pending,
            chi_tieu=self.chi_tieu_hv,
            gia_tri=Decimal("5"),
        )

        official = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do"),
            {"year": self.year},
        )
        row = self.progress_row(official, "HTKN-LOP-HV")
        self.assertEqual(row["cumulative"], "25")
        self.assertNotIn("pending", row)
        self.assertNotIn("Chờ duyệt</th>", official.content.decode())

        toggled = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do"),
            {"year": self.year, "gom_cho_duyet": "1"},
        )
        row = self.progress_row(toggled, "HTKN-LOP-HV")
        self.assertEqual(row["cumulative"], "25")
        self.assertEqual(row["pending"], "5")
        self.assertIn("Chờ duyệt</th>", toggled.content.decode())


class DrillDownTests(ReportFixtureMixin, TestCase):
    def test_count_drill_lists_approved_and_hides_draft_and_pending(self):
        draft_activity = HoatDong.objects.create(
            loai_hoat_dong=self.loai_lop,
            ten="Lớp nháp chưa duyệt",
            tu_ngay=date(self.year, self.month, 7),
            den_ngay=date(self.year, self.month, 7),
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=draft_activity,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.NHAP,
        )
        pending_activity = HoatDong.objects.create(
            loai_hoat_dong=self.loai_lop,
            ten="Lớp đang chờ duyệt",
            tu_ngay=date(self.year, self.month, 8),
            den_ngay=date(self.year, self.month, 8),
            trang_thai=TrangThaiHoatDong.DA_TO_CHUC,
        )
        PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=pending_activity,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.CHO_DUYET,
        )
        response = self.login(self.ld_tt).get(
            reverse("reporting:tien_do_chi_tiet", args=[self.chi_tieu_lop.pk]),
            {"year": self.year},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.activity.ten, content)
        self.assertNotIn(draft_activity.ten, content)
        self.assertNotIn(pending_activity.ten, content)
        self.assertIn("1 lớp", content)

    def test_sum_drill_lists_approved_phieu(self):
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do_chi_tiet", args=[self.chi_tieu_hv.pk]),
            {"year": self.year},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn(self.activity.ten, content)
        self.assertIn("25", content)
        self.assertIn(
            reverse("entry:phieu_detail", args=[self.activity_phieu.pk]),
            content,
        )

    def test_project_count_drill_lists_only_approved_support_lines(self):
        project = DuAn.objects.create(
            phong=self.htkn,
            ten_du_an="Dự án hỗ trợ M8",
            chuong_trinh="nq20",
            hinh_thuc="uom_tao",
            nam=self.year,
        )
        approved = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=project,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.DA_DUYET,
        )
        HoTroDuAn.objects.create(
            du_an=project,
            phieu=approved,
            loai_ho_tro="chuyen_gia",
            noi_dung="Tư vấn chuyên gia đã duyệt",
            so_chuyen_gia=Decimal("2"),
            ngay_ho_tro=date(self.year, self.month, 10),
        )
        draft = PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.DU_AN,
            du_an=project,
            nguoi_nhap=self.cb_htkn,
            trang_thai=TrangThaiPhieu.NHAP,
        )
        HoTroDuAn.objects.create(
            du_an=project,
            phieu=draft,
            loai_ho_tro="chuyen_gia",
            noi_dung="Tư vấn chuyên gia còn nháp",
            so_chuyen_gia=Decimal("1"),
            ngay_ho_tro=date(self.year, self.month, 11),
        )
        indicator = ChiTieu.objects.get(ma_chi_tieu="HTKN-DA-CG")
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do_chi_tiet", args=[indicator.pk]),
            {"year": self.year},
        )
        self.assertEqual(response.status_code, 200)
        content = response.content.decode()
        self.assertIn("Tư vấn chuyên gia đã duyệt", content)
        self.assertNotIn("Tư vấn chuyên gia còn nháp", content)

    def test_drill_is_scoped_to_own_department(self):
        response = self.login(self.cb_tttk).get(
            reverse("reporting:tien_do_chi_tiet", args=[self.chi_tieu_lop.pk]),
            {"year": self.year},
        )
        self.assertEqual(response.status_code, 403)

    def test_drill_has_no_chart_initialization(self):
        response = self.login(self.cb_htkn).get(
            reverse("reporting:tien_do_chi_tiet", args=[self.chi_tieu_hv.pk]),
            {"year": self.year},
        )
        self.assertEqual(response.content.decode().count("echarts.init"), 0)


class MediaExportMixin:
    @classmethod
    def setUpClass(cls):
        cls._media = tempfile.TemporaryDirectory()
        cls._settings = override_settings(MEDIA_ROOT=cls._media.name)
        cls._settings.enable()
        super().setUpClass()

    @classmethod
    def tearDownClass(cls):
        super().tearDownClass()
        cls._settings.disable()
        cls._media.cleanup()

    def export(self, client, dinh_dang, **overrides):
        data = {
            **self.month_query(phong=self.htkn.pk),
            "tiep_tuc": "1",
        }
        data.update(overrides)
        return client.post(
            reverse("reporting:xuat_bao_cao", args=[dinh_dang]),
            data,
        )


class ExportTests(ReportFixtureMixin, MediaExportMixin, TestCase):
    def test_xlsx_has_numeric_cells_and_snapshot(self):
        client = self.login(self.ld_htkn)
        response = self.export(client, "xlsx")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response["Content-Type"], "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet")
        bookmark = BaoCaoDaXuat.objects.get()
        self.assertEqual(bookmark.dinh_dang, "xlsx")
        self.assertEqual(bookmark.phong, self.htkn)
        self.assertTrue(bookmark.dinh_dang)
        self.assertTrue(bookmark.file.name.endswith(".xlsx"))
        self.assertIn("HTKN", bookmark.file.name)
        self.assertIn(f"thang-{self.month}-{self.year}", bookmark.file.name)
        self.assertEqual(
            BaoCaoDaXuatDong.objects.filter(bao_cao=bookmark).count(),
            len(rollup(ReportPeriod.month(self.year, self.month), department_id=self.htkn.pk)),
        )

        workbook = load_workbook(BytesIO(self.response_bytes(response)))
        sheet = workbook.active
        header = [cell.value for cell in sheet[1]]
        self.assertEqual(header[:7], [
            "Chỉ tiêu",
            "Đơn vị tính",
            "Kế hoạch năm",
            "Thực hiện trong kỳ",
            "Lũy kế",
            "% hoàn thành",
            "Ghi chú",
        ])
        count_row = next(
            row for row in sheet.iter_rows(min_row=2)
            if row[0].value == "Số lớp huấn luyện"
        )
        self.assertEqual(count_row[3].value, 1)
        class_row = next(
            row for row in sheet.iter_rows(min_row=2)
            if row[0].value == "Số học viên tham gia"
        )
        percent_cell = class_row[5]
        self.assertIsInstance(percent_cell.value, (int, float))
        self.assertEqual(percent_cell.number_format, "#,##0.##")
        self.assertIsInstance(class_row[2].value, (int, float))
        self.assertIsInstance(class_row[3].value, (int, float))
        self.assertEqual(class_row[3].value, 25)

    def test_two_exports_keep_first_file_unchanged(self):
        client = self.login(self.ld_htkn)
        first = self.export(client, "xlsx")
        self.assertEqual(first.status_code, 200)
        record = BaoCaoDaXuat.objects.order_by("id").first()
        first_path = Path(record.file.path)
        first_mtime = os.stat(first_path).st_mtime_ns
        first_bytes = first_path.read_bytes()

        second = self.export(client, "xlsx")
        self.assertEqual(second.status_code, 200)
        self.assertEqual(BaoCaoDaXuat.objects.count(), 2)
        self.assertEqual(os.stat(first_path).st_mtime_ns, first_mtime)
        self.assertEqual(first_path.read_bytes(), first_bytes)
        self.assertNotEqual(
            BaoCaoDaXuat.objects.order_by("id").last().file.path,
            first_path,
        )

    def test_department_user_cannot_export_another_department(self):
        client = self.login(self.cb_htkn)
        response = client.post(
            reverse("reporting:xuat_bao_cao", args=["xlsx"]),
            {
                **self.month_query(phong=self.tttk.pk),
                "tiep_tuc": "1",
            },
        )
        self.assertEqual(response.status_code, 403)

    def test_word_export_contains_class_and_formatted_number(self):
        client = self.login(self.ld_htkn)
        response = self.export(client, "docx")
        self.assertEqual(response.status_code, 200)
        document = Document(BytesIO(self.response_bytes(response)))
        text = "\n".join(paragraph.text for paragraph in document.paragraphs)
        table_text = "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn("Số lớp huấn luyện", table_text)
        self.assertIn("25", table_text)
        self.assertIn("Lớp khởi nghiệp tháng này", text)
        self.assertIn("Số liệu chưa đầy đủ", text + table_text)

    def test_center_word_export_has_three_departments(self):
        client = self.login(self.ld_tt)
        response = client.post(
            reverse("reporting:xuat_bao_cao", args=["docx"]),
            {**self.month_query(), "tiep_tuc": "1"},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("toan-trung-tam", response["Content-Disposition"])
        self.assertIn(f"thang-{self.month}-{self.year}", response["Content-Disposition"])
        document = Document(BytesIO(self.response_bytes(response)))
        table_text = "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn("PHÒNG GDCN", table_text)
        self.assertIn("PHÒNG TTTK", table_text)
        self.assertIn("PHÒNG HTKN", table_text)

    def test_tttk_effectiveness_note_goes_to_excel_and_word(self):
        client = self.login(self.cb_tttk)
        note = "Đánh giá hiệu quả TTTK"
        post = {
            **self.month_query(phong=self.tttk.pk),
            f"danh_gia_{self.tttk.pk}_{self.chi_tieu_ndt.pk}": note,
        }
        client.post(reverse("reporting:bao_cao"), post)
        xlsx = self.export(
            client,
            "xlsx",
            phong=self.tttk.pk,
        )
        workbook = load_workbook(BytesIO(self.response_bytes(xlsx)))
        values = [
            cell.value
            for row in workbook.active.iter_rows()
            for cell in row
        ]
        self.assertIn("Đánh giá hiệu quả", values)
        self.assertIn(note, values)
        docx = self.export(client, "docx", phong=self.tttk.pk)
        document = Document(BytesIO(self.response_bytes(docx)))
        table_text = "\n".join(
            cell.text
            for table in document.tables
            for row in table.rows
            for cell in row.cells
        )
        self.assertIn(note, table_text)

    def test_export_blocked_until_incomplete_data_accepted(self):
        client = self.login(self.cb_htkn)
        response = client.post(
            reverse("reporting:xuat_bao_cao", args=["xlsx"]),
            self.month_query(phong=self.htkn.pk),
        )
        self.assertEqual(response.status_code, 302)
        self.assertEqual(BaoCaoDaXuat.objects.count(), 0)


class XlsxImportTests(ReportFixtureMixin, MediaExportMixin, TestCase):
    def test_import_exported_workbook_is_read_only(self):
        client = self.login(self.ld_htkn)
        export = self.export(client, "xlsx")
        self.assertEqual(export.status_code, 200)
        before_solieu = SoLieu.objects.count()
        before_phieu = list(
            PhieuNhapLieu.objects.values_list("id", "trang_thai")
        )
        upload = SimpleUploadedFile(
            "bao-cao.xlsx",
            self.response_bytes(export),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response = client.post(
            reverse("reporting:nhap_xlsx"),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertIn("Số lớp huấn luyện", text)
        self.assertIn("Xem trước bao-cao.xlsx", text)
        self.assertEqual(SoLieu.objects.count(), before_solieu)
        self.assertEqual(
            list(PhieuNhapLieu.objects.values_list("id", "trang_thai")),
            before_phieu,
        )

    def test_import_eight_column_tttk_workbook(self):
        client = self.login(self.cb_tttk)
        export = self.export(client, "xlsx", phong=self.tttk.pk)
        self.assertEqual(export.status_code, 200)
        upload = SimpleUploadedFile(
            "tttk.xlsx",
            self.response_bytes(export),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response = client.post(
            reverse("reporting:nhap_xlsx"),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        text = response.content.decode()
        self.assertIn("Đánh giá hiệu quả", text)
        self.assertIn("Số người dùng tin đang phục vụ", text)

    def test_legacy_workbook_shows_template_error(self):
        client = self.login(self.ld_htkn)
        legacy = settings.BASE_DIR.parent / "doc" / "So lieu bao cao - P. HTKN.xlsx"
        upload = SimpleUploadedFile(
            legacy.name,
            legacy.read_bytes(),
            content_type=(
                "application/vnd.openxmlformats-officedocument."
                "spreadsheetml.sheet"
            ),
        )
        response = client.post(
            reverse("reporting:nhap_xlsx"),
            {"file": upload},
        )
        self.assertEqual(response.status_code, 200)
        self.assertIn("không đúng mẫu", response.content.decode())


class LegacyCommandTests(ReportFixtureMixin, TestCase):
    def test_inspect_legacy_workbook_prints_sheet_and_first_row(self):
        from io import StringIO

        before = SoLieu.objects.count()
        output = StringIO()
        call_command(
            "inspect_legacy_workbook",
            "So lieu bao cao - P. HTKN.xlsx",
            stdout=output,
        )
        text = output.getvalue()
        self.assertIn("PHONG HTKN", text)
        self.assertIn("STT", text)
        self.assertEqual(SoLieu.objects.count(), before)

        output = StringIO()
        call_command(
            "inspect_legacy_workbook",
            "Theo dõi nhiệm vụ phòng GDCN theo phương châm 6 rõ.xlsx",
            stdout=output,
        )
        text = output.getvalue()
        self.assertIn("Trang tính1", text)
        self.assertIn("NHIÊM VỤ VÀ SẢN PHẨM", text)
        self.assertEqual(SoLieu.objects.count(), before)
