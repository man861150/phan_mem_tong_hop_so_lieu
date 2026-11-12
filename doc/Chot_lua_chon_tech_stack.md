# Chốt lựa chọn tech stack

| | |
|---|---|
| Trạng thái | Đã chốt |
| Ngày chốt | 2026-11-12 |
| Phạm vi giai đoạn này | Môi trường development trên localhost |
| Người quyết định | Solo developer của phần mềm tổng hợp số liệu — Trung tâm Khởi nghiệp sáng tạo TP.HCM |

## Quyết định

Xây dựng phần mềm nhập liệu, tổng hợp số liệu và báo cáo hoạt động bằng **một Django monolith**: Django templates + Tabler + HTMX 2.

Một repo, một ngôn ngữ (Python), một process. Giao diện tiếng Việt, server-rendered. Chưa tách frontend/backend, chưa làm API công khai.

Giai đoạn này chỉ chạy trên máy dev bằng `runserver` tại `http://127.0.0.1:8000`. Testing tự động và triển khai (Docker, VPS, backup) nằm ngoài phạm vi.

## Stack đã chốt

| Hạng mục | Lựa chọn | Ghi chú |
|---|---|---|
| UI | Django templates + Tabler (Bootstrap 5) + HTMX 2 | CSS/JS để sẵn trong `static/vendor/`. Không dùng Node, không dùng SPA. |
| Tương tác cục bộ | Alpine.js | Chỉ trong các lưới nhập liệu có chia đối tượng / lĩnh vực. |
| Form | Django forms dựng từ danh mục chỉ tiêu | `BieuMauChiTieu` quyết định trường nào hiện ra. Ràng buộc liên trường nằm trong `clean()`. |
| Backend | Django 5.2 LTS (`>=5.2.19,<5.3`) | Hỗ trợ bảo mật đến tháng 4/2028. Không có API riêng trong v1. |
| Cơ sở dữ liệu | PostgreSQL 17 | UTF-8, collation ICU `vi-VN`. Django migrations. |
| Xác thực | Session cookie của Django + django-axes | Tài khoản tự host. Bốn vai trò: cán bộ nhập liệu, lãnh đạo phòng, lãnh đạo Trung tâm, quản trị hệ thống. |
| Phân quyền | Một trường `role` và `phong_id` | Lãnh đạo phòng bao gồm quyền nhập liệu. Lãnh đạo Trung tâm chỉ xem. Lọc dữ liệu theo phòng ở một queryset helper. |
| Tổng hợp số | Một hàm `reporting.rollup` | Dashboard, Excel và Word cùng gọi hàm này. SQL tính tổng, đếm, lũy kế, giá trị mới nhất. Python tính tỷ lệ, % kế hoạch và cờ chậm tiến độ. |
| Excel | openpyxl | Đọc file hiện có và xuất bảng kỳ báo cáo. |
| Word | docxtpl | Điền vào file `.docx` mẫu của phòng. |
| Biểu đồ | Apache ECharts 5, để trong `static/vendor/` | Tối đa hai biểu đồ. Màn tiến độ chính là bảng. |
| Audit | django-simple-history + `LichSuXuLy` | History ghi ai sửa trường nào. `LichSuXuLy` ghi ý kiến gửi / duyệt / trả lại / mở lại. |
| Báo cáo đã phát hành | Bảng `BaoCaoDaXuat` (file + snapshot dòng số liệu) | Số trên dashboard là số tại thời điểm xem. File đã tải giữ nguyên sau khi mở lại phiếu. |
| Ngôn ngữ giao diện | Tiếng Việt trong template | Không làm giao diện tiếng Anh. Tên biến và tên app trong code dùng tiếng Anh. |
| Công cụ dev | `uv`, ruff | `uv.lock` là nguồn phụ thuộc. ruff để format và lint khi sửa code. |

### Phụ thuộc cài cho localhost

```text
Django>=5.2.19,<5.3
psycopg[binary]>=3.2
django-htmx>=1.21
django-simple-history>=3.7
django-axes>=7
openpyxl>=3.1
docxtpl>=0.19
django-environ>=0.11
```

Dev:

```text
ruff>=0.8
```

Khóa đúng bản patch bằng `uv.lock` vào ngày khởi tạo project.

### App trong repo

```text
solieu/
  manage.py
  config/            # settings, urls, wsgi
  apps/
    accounts/        # người dùng, vai trò, phạm vi phòng
    catalog/         # phòng ban, chỉ tiêu, kế hoạch năm, danh mục, biểu mẫu
    activities/      # loại hoạt động, hoạt động, đơn vị phối hợp, dự án
    entry/           # phiếu nhập liệu, số liệu, hỗ trợ dự án, duyệt
    reporting/       # rollup.py, xuất xlsx, xuất docx, báo cáo đã xuất
  templates/
  report_templates/
  fixtures/
  static/vendor/     # tabler, htmx, alpine, echarts
```

Mô hình dữ liệu bám tài liệu `Phan_tich_thiet_ke_yeu_cau_phan_mem.docx`: chỉ tiêu dạng dòng (`SoLieu`), không tạo một cột cho mỗi chỉ tiêu, không lưu toàn bộ phiếu dưới dạng JSON. Sáu cách tổng hợp: tổng, đếm, lũy kế, tỷ lệ, trung bình, mới nhất.

## Phạm vi localhost

Chạy trên macOS của máy dev.

- PostgreSQL 17 cài trên máy (Homebrew).
- Django `runserver` tại `127.0.0.1:8000`.
- Biến môi trường trong `.env`, không commit file này.
- Múi giờ `Asia/Ho_Chi_Minh`. `USE_TZ = True`. Số lưu kiểu `numeric`, định dạng `1.234` chỉ khi hiển thị và khi xuất file.

`.env`:

```bash
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=true
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DATABASE_URL=postgres://solieu:solieu@127.0.0.1:5432/solieu
```

### Cài và chạy

```bash
brew install postgresql@17 uv
brew services start postgresql@17

# Tạo role và database một lần. Collation tiếng Việt để ORDER BY tên đúng.
createuser -P solieu
psql -d postgres -c "CREATE DATABASE solieu OWNER solieu LOCALE_PROVIDER icu ICU_LOCALE 'vi-VN' TEMPLATE template0;"

mkdir solieu && cd solieu
uv init
uv add "Django>=5.2.19,<5.3" "psycopg[binary]>=3.2" \
  "django-htmx>=1.21" "django-simple-history>=3.7" "django-axes>=7" \
  "openpyxl>=3.1" "docxtpl>=0.19" "django-environ>=0.11"
uv add --dev "ruff>=0.8"
uv run django-admin startproject config .

uv run python manage.py migrate
uv run python manage.py createsuperuser
uv run python manage.py runserver
```

Mở `http://127.0.0.1:8000/`. Catalog (phòng, chỉ tiêu, biểu mẫu, danh mục) quản trị qua Django admin tại `/admin/`. Cán bộ nhập liệu dùng các màn hình template riêng, không dùng admin.

Ba màn hình làm trước:

1. Trang chủ sau đăng nhập: phiếu nháp / bị trả lại, hàng chờ duyệt, % hoàn thành theo phòng.
2. Tạo hoạt động và phiếu kết quả lớp huấn luyện của Phòng HTKN, sinh field từ `BieuMauChiTieu`.
3. Xem báo cáo kỳ của phòng và tải Excel.

Phòng HTKN là phòng dùng thử đầu tiên.

## Ngoài phạm vi giai đoạn này

Testing và deploy không làm bây giờ. Khi tới giai đoạn đó, hướng đã chọn vẫn là:

- Test: pytest trên quy tắc tổng hợp, kiểm tra tổng các phần chia, phạm vi phòng, và vòng đời duyệt phiếu.
- Deploy: Docker Compose (gunicorn, PostgreSQL, Caddy) trên một máy Linux, backup `pg_dump` hằng đêm.

Các lựa chọn đó chưa cần cài. Không đưa `pytest`, `factory-boy`, `gunicorn`, `whitenoise`, Dockerfile hay docker-compose vào project ở giai đoạn localhost.
