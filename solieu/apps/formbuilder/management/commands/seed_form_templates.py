"""Idempotent sample template for the HTKN training-class form."""

from django.core.exceptions import ValidationError
from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import User
from apps.accounts.roles import Role
from apps.catalog.models import LoaiHoatDong, PhongBan
from apps.formbuilder.models import FormRule, FormTemplate
from apps.formbuilder.services import (
    add_field,
    add_option,
    add_section,
    build_scope_key,
    publish_template,
)


class Command(BaseCommand):
    help = (
        "Tạo biểu mẫu đã xuất bản cho Hoạt động / Lớp huấn luyện của phòng HTKN. "
        "Chạy lại bỏ qua nếu phạm vi đó đã có biểu mẫu đang hoạt động."
    )

    def handle(self, *args, **options):
        phong = PhongBan.objects.filter(ma_phong="HTKN").first()
        if phong is None:
            raise CommandError("Không tìm thấy phòng HTKN.")
        activity_type = LoaiHoatDong.objects.filter(
            phong=phong,
            ten_loai="Lớp huấn luyện",
        ).first()
        if activity_type is None:
            raise CommandError(
                "Không tìm thấy loại hoạt động “Lớp huấn luyện” của HTKN."
            )
        user = (
            User.objects.filter(role=Role.SYSTEM_ADMIN).order_by("id").first()
            or User.objects.order_by("id").first()
        )
        if user is None:
            raise CommandError("Chưa có người dùng để ghi người tạo biểu mẫu.")
        scope_key = build_scope_key("hoat_dong", activity_type.pk, None)
        existing = FormTemplate.objects.filter(
            phong=phong,
            scope_key=scope_key,
            is_active=True,
        ).first()
        if existing is not None:
            self.stdout.write(
                "Đã có biểu mẫu đang hoạt động cho Lớp huấn luyện. Bỏ qua."
            )
            return
        try:
            template = _build(phong, activity_type, user)
        except ValidationError as exc:
            raise CommandError("; ".join(exc.messages)) from exc
        self.stdout.write(
            f"Đã tạo “{template.name}”, phiên bản xuất bản "
            f"{template.current_published.version}, bản nháp "
            f"{template.current_draft.version}."
        )


@transaction.atomic
def _build(phong, activity_type, user):
    from apps.formbuilder.services import create_template

    template = create_template(
        phong=phong,
        name="Lớp huấn luyện",
        description="Biểu mẫu bổ sung cho lớp huấn luyện của phòng HTKN.",
        function_type="hoat_dong",
        user=user,
        activity_type=activity_type,
    )
    draft = template.current_draft
    section = add_section(draft, "Thông tin bổ sung")
    count = add_field(
        draft,
        "integer",
        section,
        label="Số lượng đại biểu",
        key="cf_so_luong_dai_bieu",
    )
    count.required = True
    count.min_value = 0
    count.save()
    partner = add_field(
        draft,
        "lookup",
        section,
        label="Đơn vị chủ trì",
        key="cf_don_vi_chu_tri",
    )
    partner.catalog_source = "don_vi_phoi_hop"
    partner.save()
    channel = add_field(
        draft,
        "select",
        section,
        label="Hình thức truyền thông",
        key="cf_hinh_thuc_truyen_thong",
    )
    for label in ("Trực tiếp", "Trực tuyến", "Kết hợp"):
        add_option(channel, label, label)
    upload = add_field(
        draft,
        "file",
        section,
        label="Tài liệu đính kèm",
        key="cf_tai_lieu",
    )
    upload.allowed_extensions = "pdf,docx"
    upload.max_file_size_mb = 10
    upload.save()
    add_field(draft, "textarea", section, label="Ghi chú", key="cf_ghi_chu")
    meeting = add_field(
        draft,
        "url",
        section,
        label="Đường dẫn phòng họp",
        key="cf_duong_dan_phong_hop",
    )
    FormRule.objects.create(
        version=draft,
        source_field_key=channel.key,
        operator="equals",
        compare_value="Trực tuyến",
        action="require",
        target_field_key=meeting.key,
        order=1,
    )
    publish_template(template, user)
    template.refresh_from_db()
    add_field(
        template.current_draft,
        "text",
        template.current_draft.sections.get(title="Thông tin bổ sung"),
        label="Ghi chú nội bộ",
        key="cf_ghi_chu_noi_bo",
    )
    return template
