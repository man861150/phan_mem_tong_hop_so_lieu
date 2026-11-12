"""Idempotent localhost departments and the four role accounts."""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.catalog.models import PhongBan

# Localhost only. Printed by --help. Not for any shared environment.
DEV_PASSWORDS = {
    "cb.htkn": "Canbo-local-1",
    "ld.htkn": "Lanhdao-phong-1",
    "ld.tt": "Lanhdao-tt-1",
    "admin": "Quantri-local-1",
}

DEPARTMENTS = (
    ("GDCN", "Phòng Giao dịch công nghệ"),
    ("TTTK", "Phòng Thông tin – Thống kê"),
    ("HTKN", "Phòng HTKN"),
    ("BGĐ", "Ban Giám đốc"),
)

# username, ho_ten, role, ma_phong or None, is_staff, is_superuser
USERS = (
    ("cb.htkn", "Cán bộ HTKN", Role.ENTRY_OFFICER, "HTKN", False, False),
    ("ld.htkn", "Lãnh đạo phòng HTKN", Role.DEPARTMENT_HEAD, "HTKN", False, False),
    ("ld.tt", "Lãnh đạo Trung tâm", Role.CENTER_HEAD, "BGĐ", False, False),
    ("admin", "Quản trị hệ thống", Role.SYSTEM_ADMIN, None, True, True),
)


class Command(BaseCommand):
    help = (
        "Đảm bảo phòng GDCN, TTTK, HTKN, BGĐ và bốn tài khoản localhost. "
        "Chạy lại không tạo bản ghi trùng. Mật khẩu chỉ dùng trên máy dev: "
        + ", ".join(f"{username}={password}" for username, password in DEV_PASSWORDS.items())
        + "."
    )

    def handle(self, *args, **options):
        departments = {}
        for ma_phong, ten_phong in DEPARTMENTS:
            phong = PhongBan.objects.filter(ma_phong=ma_phong).first()
            created = phong is None
            if created:
                phong = PhongBan(ma_phong=ma_phong)
            phong.ten_phong = ten_phong
            phong.dang_su_dung = True
            phong.save()
            departments[ma_phong] = phong
            self.stdout.write(f"phong {ma_phong}: {'created' if created else 'kept'}")

        for username, ho_ten, role, ma_phong, is_staff, is_superuser in USERS:
            user = User.objects.filter(username=username).first()
            created = user is None
            if created:
                user = User(username=username)
            user.ho_ten = ho_ten
            user.email = f"{username}@localhost"
            user.role = role
            user.phong = departments[ma_phong] if ma_phong else None
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            user.set_password(DEV_PASSWORDS[username])
            user.save()
            self.stdout.write(f"user {username}: {'created' if created else 'kept'}")

        self.stdout.write(
            f"departments={PhongBan.objects.filter(ma_phong__in=[row[0] for row in DEPARTMENTS]).count()} "
            f"users={User.objects.filter(username__in=DEV_PASSWORDS).count()}"
        )
