"""Task-oriented grouping and guidance for the default admin site."""

from django.contrib.admin import AdminSite
from django.template.response import TemplateResponse
from django.urls import reverse

PERIOD_GUIDANCE = (
    "Chọn một hoặc nhiều kỳ trong bảng, rồi chọn hành động Mở kỳ hoặc Khóa kỳ. "
    "Kỳ đang mở cho phép nhập liệu. Kỳ đã khóa không nhận số liệu mới."
)
DON_VI_GUIDANCE = (
    "Để gộp đơn vị trùng: chọn ít nhất hai dòng, rồi chọn hành động "
    "Gộp đơn vị trùng. Hệ thống giữ bản có tên đã bỏ khoảng trắng thừa "
    "và mã nhỏ nhất, chuyển liên kết sang bản đó, rồi xóa các bản trùng."
)
LINH_VUC_GUIDANCE = (
    "Nút Nạp từ fixtures/linh_vuc.csv tạo mới hoặc cập nhật lĩnh vực theo "
    "hệ thống và mã. Dòng không có trong tệp được giữ nguyên, không bị xóa."
)
READONLY_GUIDANCE = (
    "Dữ liệu này được nhập và duyệt trong ứng dụng chính. "
    "Trang này chỉ để tra cứu và xem lịch sử thay đổi."
)

# (app_label, model_name, title, one-sentence description)
DOMAINS = (
    {
        "key": "users",
        "name": "Quản lý người dùng & Phân quyền",
        "description": (
            "Tạo tài khoản, gán vai trò và phòng ban, "
            "và mở khóa khi đăng nhập sai quá nhiều lần."
        ),
        "read_only": False,
        "models": (
            (
                "accounts",
                "user",
                "Người dùng",
                "Tài khoản, vai trò, phòng ban và trạng thái hoạt động. "
                "Dùng khi thêm người hoặc đổi quyền.",
            ),
            (
                "axes",
                "accessattempt",
                "Tài khoản bị khóa tạm",
                "Các lượt đăng nhập sai còn hiệu lực. "
                "Xóa dòng hoặc dùng Mở khóa tài khoản trên Người dùng.",
            ),
        ),
    },
    {
        "key": "periods",
        "name": "Kỳ báo cáo & Kế hoạch năm",
        "description": (
            "Mở hoặc khóa kỳ nhập liệu, và nhập số kế hoạch năm theo chỉ tiêu."
        ),
        "read_only": False,
        "models": (
            (
                "catalog",
                "kybaocao",
                "Kỳ báo cáo",
                "Mở kỳ để cho nhập liệu, hoặc khóa kỳ khi đã chốt số.",
            ),
            (
                "catalog",
                "chitieukehoach",
                "Chỉ tiêu kế hoạch",
                "Giá trị kế hoạch năm của từng chỉ tiêu và phòng ban.",
            ),
        ),
    },
    {
        "key": "catalog",
        "name": "Cấu hình Danh mục & Chỉ tiêu",
        "description": (
            "Thiết lập phòng ban, nhóm chỉ tiêu, chỉ tiêu và biểu mẫu hoạt động "
            "trước khi cán bộ nhập liệu."
        ),
        "read_only": False,
        "models": (
            (
                "catalog",
                "phongban",
                "Phòng ban",
                "Phòng thuộc Trung tâm và các nhóm chỉ tiêu của phòng.",
            ),
            (
                "catalog",
                "nhomchitieu",
                "Nhóm chỉ tiêu",
                "Mảng chỉ tiêu trong một phòng. Dùng khi tách nhóm báo cáo.",
            ),
            (
                "catalog",
                "chitieu",
                "Chỉ tiêu",
                "Cách ghi nhận, cách tổng hợp và giới hạn giá trị của từng chỉ tiêu.",
            ),
            (
                "catalog",
                "loaihoatdong",
                "Loại hoạt động",
                "Loại hoạt động của từng phòng và các chỉ tiêu gắn vào biểu mẫu.",
            ),
            (
                "catalog",
                "bieumauchitieu",
                "Biểu mẫu chỉ tiêu",
                "Chỉ tiêu nào xuất hiện trên biểu mẫu của một loại hoạt động.",
            ),
        ),
    },
    {
        "key": "lookups",
        "name": "Danh mục dùng chung",
        "description": (
            "Bảng tra cứu dùng lại trên phiếu: đối tượng, lĩnh vực, nguồn và "
            "đơn vị phối hợp."
        ),
        "read_only": False,
        "models": (
            (
                "catalog",
                "danhmucdoituong",
                "Đối tượng",
                "Nhóm đối tượng dùng khi phân loại số liệu và hoạt động.",
            ),
            (
                "catalog",
                "danhmuclinhvuc",
                "Lĩnh vực",
                "Cây lĩnh vực QĐ 36 và TT 24. Có thể nạp lại từ tệp CSV.",
            ),
            (
                "catalog",
                "nguonsolieu",
                "Nguồn số liệu",
                "Nguồn được phép chọn khi nhập một chỉ tiêu.",
            ),
            (
                "activities",
                "donviphoihop",
                "Đơn vị phối hợp",
                "Đơn vị cùng thực hiện hoạt động. Gộp các dòng trùng tên tại đây.",
            ),
        ),
    },
    {
        "key": "audit",
        "name": "Tra cứu & Kiểm tra dữ liệu nghiệp vụ",
        "description": (
            "Phiếu, số liệu, hoạt động, dự án và báo cáo đã xuất. "
            "Chỉ xem để đối soát, không sửa tại đây."
        ),
        "read_only": True,
        "models": (
            (
                "entry",
                "phieunhaplieu",
                "Phiếu nhập liệu",
                "Phiếu hoạt động, phiếu tháng và phiếu dự án cùng trạng thái duyệt.",
            ),
            (
                "entry",
                "solieu",
                "Số liệu",
                "Từng giá trị đã nhập trên phiếu. Dùng khi cần đối soát một chỉ tiêu.",
            ),
            (
                "activities",
                "hoatdong",
                "Hoạt động",
                "Hoạt động đã khai báo trong ứng dụng chính.",
            ),
            (
                "activities",
                "duan",
                "Dự án",
                "Dự án của các phòng. Xem nội dung, không sửa tại cổng này.",
            ),
            (
                "entry",
                "hotroduan",
                "Hỗ trợ dự án",
                "Các lần hỗ trợ gắn với dự án và phiếu.",
            ),
            (
                "entry",
                "lichsuxuly",
                "Lịch sử xử lý",
                "Ai đã gửi, duyệt, trả lại hoặc mở lại từng phiếu.",
            ),
            (
                "reporting",
                "baocaodaxuat",
                "Báo cáo đã xuất",
                "Tệp báo cáo đã lập và các dòng số tại thời điểm xuất.",
            ),
        ),
    },
)


class GuidanceMixin:
    """Show a fixed explanation above a changelist and a change form."""

    guidance = ""
    change_list_template = "admin/portal/change_list.html"
    change_form_template = "admin/portal/change_form.html"

    def changelist_view(self, request, extra_context=None):
        extra = {"guidance": self.guidance}
        extra.update(extra_context or {})
        return super().changelist_view(request, extra)

    def changeform_view(self, request, object_id=None, form_url="", extra_context=None):
        extra = {"guidance": self.guidance}
        extra.update(extra_context or {})
        return super().changeform_view(request, object_id, form_url, extra)


class SolieuAdminSite(AdminSite):
    site_header = "Cổng quản trị hệ thống"
    site_title = "Quản trị số liệu"
    index_title = "Trung tâm điều hành"
    index_template = "admin/index.html"
    site_url = "/"

    def each_context(self, request):
        context = super().each_context(request)
        user = request.user
        if getattr(user, "is_authenticated", False):
            from apps.accounts.roles import Role
            from config.admin_display import ROLE_TONE

            context["portal_full_name"] = (
                getattr(user, "ho_ten", "") or user.get_username()
            )
            role = getattr(user, "role", "")
            context["portal_role_label"] = dict(Role.choices).get(role, "")
            context["portal_role_tone"] = ROLE_TONE.get(role, "inactive")
        return context

    def get_app_list(self, request, app_label=None):
        if app_label:
            return super().get_app_list(request, app_label)
        built = self._build_app_dict(request)
        by_key = {}
        for app in built.values():
            for model in app["models"]:
                by_key[(app["app_label"], model["object_name"].lower())] = model
        domains = []
        for spec in DOMAINS:
            models = []
            for app_label_key, model_name, title, description in spec["models"]:
                model = by_key.get((app_label_key, model_name))
                if model is None:
                    continue
                models.append(
                    {
                        **model,
                        "name": title,
                        "description": description,
                    }
                )
            if not models:
                continue
            domains.append(
                {
                    "name": spec["name"],
                    "app_label": spec["key"],
                    "app_url": f"/admin/#{spec['key']}",
                    "has_module_perms": True,
                    "description": spec["description"],
                    "read_only": spec["read_only"],
                    "models": models,
                }
            )
        return domains

    def index(self, request, extra_context=None):
        app_list = self.get_app_list(request)
        for app in app_list:
            for model in app["models"]:
                model_admin = self._registry[model["model"]]
                model["count"] = model_admin.get_queryset(request).count()
        context = {
            **self.each_context(request),
            "title": self.index_title,
            "subtitle": None,
            "app_list": app_list,
            "portal_kpis": build_kpis(),
            "lockout": lockout_summary(),
            **(extra_context or {}),
        }
        request.current_app = self.name
        return TemplateResponse(
            request, self.index_template or "admin/index.html", context
        )


def build_kpis():
    from django.db.models import Count, Q
    from django.utils import timezone

    from apps.accounts.models import User
    from apps.accounts.roles import Role
    from apps.catalog.models import ChiTieu, KyBaoCao, PhongBan, TrangThaiKy

    year = timezone.localdate().year
    users = User.objects.filter(is_active=True).aggregate(
        total=Count("id"),
        system_admin=Count("id", filter=Q(role=Role.SYSTEM_ADMIN)),
        center_head=Count("id", filter=Q(role=Role.CENTER_HEAD)),
        department_head=Count("id", filter=Q(role=Role.DEPARTMENT_HEAD)),
        entry_officer=Count("id", filter=Q(role=Role.ENTRY_OFFICER)),
    )
    periods = KyBaoCao.objects.filter(nam=year).aggregate(
        mo=Count("id", filter=Q(trang_thai=TrangThaiKy.MO)),
        khoa=Count("id", filter=Q(trang_thai=TrangThaiKy.KHOA)),
    )
    return {
        "year": year,
        "users": users,
        "periods": periods,
        "departments": PhongBan.objects.filter(dang_su_dung=True).count(),
        "indicators": ChiTieu.objects.filter(dang_su_dung=True).count(),
    }


def lockout_summary():
    from axes.models import AccessAttempt
    from django.conf import settings
    from django.utils import timezone

    limit = settings.AXES_FAILURE_LIMIT
    rows = AccessAttempt.objects.filter(failures_since_start__gte=limit)
    cooloff = settings.AXES_COOLOFF_TIME
    if cooloff is not None:
        rows = rows.filter(attempt_time__gte=timezone.now() - cooloff)
    usernames = {name for name in rows.values_list("username", flat=True) if name}
    return {
        "count": len(usernames),
        "url": reverse("admin:axes_accessattempt_changelist"),
    }


def install():
    from django.contrib import admin

    admin.site.__class__ = SolieuAdminSite
    admin.site.site_header = SolieuAdminSite.site_header
    admin.site.site_title = SolieuAdminSite.site_title
    admin.site.index_title = SolieuAdminSite.index_title
    admin.site.index_template = SolieuAdminSite.index_template
