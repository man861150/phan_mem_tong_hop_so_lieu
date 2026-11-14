"""Shared departments, roles, and template helpers for formbuilder tests."""

from datetime import date

from django.test import Client, TestCase

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.activities.models import HoatDong, TrangThaiHoatDong
from apps.catalog.models import LoaiHoatDong, NhomChiTieu, PhongBan
from apps.entry.models import LoaiPhieu, PhieuNhapLieu
from apps.formbuilder.services import create_template


class FormFixture(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.htkn = PhongBan.objects.create(ma_phong="HTKN", ten_phong="Phòng HTKN")
        cls.gdcn = PhongBan.objects.create(ma_phong="GDCN", ten_phong="Phòng GDCN")
        cls.loai = LoaiHoatDong.objects.create(
            phong=cls.htkn,
            ten_loai="Lớp huấn luyện",
        )
        cls.loai_other = LoaiHoatDong.objects.create(
            phong=cls.gdcn,
            ten_loai="Techmart",
        )
        cls.nhom = NhomChiTieu.objects.create(phong=cls.htkn, ten_mang="HTKN-HL")
        cls.nhom_other = NhomChiTieu.objects.create(phong=cls.gdcn, ten_mang="GDCN")
        cls.head = User.objects.create_user(
            username="ld.htkn",
            ho_ten="Lãnh đạo HTKN",
            role=Role.DEPARTMENT_HEAD,
            phong=cls.htkn,
            password="test-pass-1",
        )
        cls.head_other = User.objects.create_user(
            username="ld.gdcn",
            ho_ten="Lãnh đạo GDCN",
            role=Role.DEPARTMENT_HEAD,
            phong=cls.gdcn,
            password="test-pass-1",
        )
        cls.officer = User.objects.create_user(
            username="cb.htkn",
            ho_ten="Cán bộ HTKN",
            role=Role.ENTRY_OFFICER,
            phong=cls.htkn,
            password="test-pass-1",
        )
        cls.center = User.objects.create_user(
            username="ld.tt",
            ho_ten="Lãnh đạo Trung tâm",
            role=Role.CENTER_HEAD,
            password="test-pass-1",
        )
        cls.admin = User.objects.create_user(
            username="admin",
            ho_ten="Quản trị hệ thống",
            role=Role.SYSTEM_ADMIN,
            password="test-pass-1",
        )

    def login(self, user):
        client = Client(HTTP_HOST="localhost")
        client.force_login(user)
        return client

    def make_template(self, **overrides):
        values = {
            "phong": self.htkn,
            "name": "Biểu mẫu lớp",
            "function_type": "hoat_dong",
            "user": self.head,
            "activity_type": self.loai,
        }
        values.update(overrides)
        return create_template(**values)

    def make_activity(self, **overrides):
        values = {
            "loai_hoat_dong": self.loai,
            "ten": "Lớp tháng 11",
            "tu_ngay": date(2026, 11, 5),
            "den_ngay": date(2026, 11, 7),
            "trang_thai": TrangThaiHoatDong.DA_TO_CHUC,
        }
        values.update(overrides)
        return HoatDong.objects.create(**values)

    def make_phieu(self, activity=None):
        activity = activity or self.make_activity()
        return PhieuNhapLieu.objects.create(
            phong=self.htkn,
            loai_phieu=LoaiPhieu.HOAT_DONG,
            hoat_dong=activity,
            nguoi_nhap=self.officer,
        )
