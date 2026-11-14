"""Idempotent localhost departments and the role accounts."""

from django.core.management.base import BaseCommand

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.catalog.models import PhongBan

# Localhost only. Printed by --help. Not for any shared environment.
DEV_PASSWORDS = {
    "cb.gdcn": "Canbo-local-1",
    "ld.gdcn": "Lanhdao-phong-1",
    "cb.tttk": "Canbo-local-1",
    "ld.tttk": "Lanhdao-phong-1",
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
    ("cb.gdcn", "Cán bộ GDCN (mẫu)", Role.ENTRY_OFFICER, "GDCN", False, False),
    ("ld.gdcn", "Lãnh đạo phòng GDCN (mẫu)", Role.DEPARTMENT_HEAD, "GDCN", False, False),
    ("cb.tttk", "Cán bộ TTTK (mẫu)", Role.ENTRY_OFFICER, "TTTK", False, False),
    ("ld.tttk", "Lãnh đạo phòng TTTK (mẫu)", Role.DEPARTMENT_HEAD, "TTTK", False, False),
    ("cb.htkn", "Cán bộ HTKN", Role.ENTRY_OFFICER, "HTKN", False, False),
    ("ld.htkn", "Lãnh đạo phòng HTKN", Role.DEPARTMENT_HEAD, "HTKN", False, False),
    ("ld.tt", "Lãnh đạo Trung tâm", Role.CENTER_HEAD, "BGĐ", False, False),
    ("admin", "Quản trị hệ thống", Role.SYSTEM_ADMIN, None, True, True),
)


def seed_localhost() -> list[str]:
    """Ensure departments and accounts without rewriting unchanged rows."""
    lines = []
    departments = {}
    for ma_phong, ten_phong in DEPARTMENTS:
        phong = PhongBan.objects.filter(ma_phong=ma_phong).first()
        created = phong is None
        if created:
            phong = PhongBan(ma_phong=ma_phong)
        changed = (
            created
            or phong.ten_phong != ten_phong
            or not phong.dang_su_dung
        )
        if changed:
            phong.ten_phong = ten_phong
            phong.dang_su_dung = True
            phong.save()
        departments[ma_phong] = phong
        lines.append(f"phong {ma_phong}: {'created' if created else 'kept'}")

    for username, ho_ten, role, ma_phong, is_staff, is_superuser in USERS:
        user = User.objects.filter(username=username).first()
        created = user is None
        if created:
            user = User(username=username)
        desired_phong = departments[ma_phong] if ma_phong else None
        changed = (
            created
            or user.ho_ten != ho_ten
            or user.email != f"{username}@localhost"
            or user.role != role
            or user.phong_id != getattr(desired_phong, "pk", None)
            or user.is_staff != is_staff
            or user.is_superuser != is_superuser
            or not user.is_active
        )
        password_changed = created or not user.check_password(
            DEV_PASSWORDS[username]
        )
        if changed or password_changed:
            user.ho_ten = ho_ten
            user.email = f"{username}@localhost"
            user.role = role
            user.phong = desired_phong
            user.is_staff = is_staff
            user.is_superuser = is_superuser
            user.is_active = True
            if password_changed:
                user.set_password(DEV_PASSWORDS[username])
            user.save()
        lines.append(f"user {username}: {'created' if created else 'kept'}")

    lines.append(
        "departments="
        f"{PhongBan.objects.filter(ma_phong__in=[row[0] for row in DEPARTMENTS]).count()} "
        f"users={User.objects.filter(username__in=DEV_PASSWORDS).count()}"
    )
    return lines


class Command(BaseCommand):
    help = (
        "Đảm bảo phòng GDCN, TTTK, HTKN, BGĐ và tám tài khoản localhost. "
        "Chạy lại không tạo bản ghi trùng. Mật khẩu chỉ dùng trên máy dev: "
        + ", ".join(
            f"{username}={password}" for username, password in DEV_PASSWORDS.items()
        )
        + "."
    )

    def handle(self, *args, **options):
        for line in seed_localhost():
            self.stdout.write(line)
