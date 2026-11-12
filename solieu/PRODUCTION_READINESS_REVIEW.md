# Đánh giá mức sẵn sàng đưa vào sử dụng thực tế

**Ngày đánh giá:** 12/11/2026. Chỉ đọc mã nguồn, tài liệu và DB localhost; không thay đổi ứng dụng, migration hay dữ liệu.

## 1. Kết luận điều hành

**Chưa sẵn sàng chạy pilot có dữ liệu thật hoặc đưa vào production.** Ba blocker lớn nhất: (1) cấu hình hiện tại `DEBUG=True`, `SECRET_KEY` placeholder 9 ký tự và `/media/` được phục vụ công khai; (2) chưa có môi trường triển khai, backup/restore đã diễn tập và giám sát; (3) superuser được seed có thể sửa phiếu/số liệu ngoài workflow, trong khi lưu nháp/khóa kỳ chưa đồng bộ bằng khóa giao dịch. Ngoài blocker vận hành, cây QĐ36/TT24 chính thức chưa có, thang hài lòng 1–5 không được giới hạn và Excel có thể mất độ chính xác. `ruff`, `check`, migration check sạch; 118 test Django chạy qua nhưng không chứng minh an toàn triển khai.

## 2. Phạm vi đã đối chiếu

- `doc/Phan_tich_thiet_ke_yeu_cau_phan_mem.docx`: mục 2, 3, 5, 6; Bảng 3–7, 18, 21–34 và UC01–UC19.
- Toàn bộ `doc/Chot_lua_chon_tech_stack.md`; giai đoạn trước chỉ localhost, testing/deploy nằm ngoài scope (dòng 7–16, 130–137).
- `solieu/TASKS.md`: §4.1–4.3, §4.4–4.6, Definition of Done §5; 83 task và Q1–Q13. Mapping app-task: `accounts`↔M1; `catalog`↔M1–M2; `activities`↔M2–M3; `entry`↔M4–M5; `reporting`↔M6–M9; `config`/templates↔M0/M8/M10. Traceability `TASKS.md:1164-1209`.
- Kiểm kê models/views/urls/forms/admin/tests theo app; templates, report_templates, static/vendor và migrations. Chạy baseline theo yêu cầu, thêm `uv run python manage.py test`; kiểm tra DB bằng SELECT và URL bằng Django test client.
- `doc/Huong_dan_su_dung_can_bo_nhap_lieu.md` có 427 dòng nhưng chỉ dành cho cán bộ nhập liệu. Chưa thấy manual lãnh đạo/quản trị hoặc runbook vận hành.

## 3. Bảng tổng hợp

| Hạng mục | Trạng thái | Phân loại (in-scope gap / production gap / improvement) | Mức độ | Bằng chứng | Khuyến nghị |
|---|---|---|---|---|---|
| Cây lĩnh vực QĐ36/TT24 | Thiếu danh mục chính thức; DB localhost 0 mã. CSV có 3 dòng QĐ36 mẫu, không TT24. | In-scope gap | High | `fixtures/linh_vuc.csv:1-4`; `load_linh_vuc.py:25-30`; TASKS Q1 `1228` | Lấy CSV chuẩn có chủ sở hữu/sign-off, nạp và đối chiếu mã/cấp/cây. |
| Độ đầy đủ catalog chỉ tiêu | DB có 96 chỉ tiêu/81 biểu mẫu; chưa có biên bản đối chiếu từng dòng với nguồn chính thức đã ký. | Production gap | Medium | `catalog/seed_data.py`; DB counts Phụ lục D; Bảng 5–7 trong requirements | Chủ ba phòng xác nhận từng mã/chỉ tiêu/form/nguồn/kế hoạch trước dữ liệu chính thức. |
| Thang hài lòng 1–5 | Không chặn >5; probe cho `TTTK-HT-HL=6` hợp lệ. | In-scope gap | High | `seed_data.py:663-672`; `entry/forms.py:36-49,309-342`; Phụ lục B | Thêm giới hạn 1–5 và test submit/rollup. |
| Độ chính xác Excel | Decimal chuyển sang float; `12345678901234.1234` đọc lại `12345678901234.12`. | In-scope gap | High | `xlsx_export.py:30-35,93-109`; Phụ lục B | Chốt giới hạn số có nghĩa, không âm thầm làm tròn; thêm round-trip tests. |
| Báo cáo đặc thù phòng | Export thiếu breakdown TTTK, danh sách trung tâm, nội dung/kết quả nhiệm vụ HTKN. | In-scope gap | High | `report_data.py:435-458,488-538`; `xlsx_export.py:68-119`; `docx_export.py:42-61,85-117` | Hoàn thiện Word/Excel theo Bảng 6–7, 18 và duyệt mẫu. |
| Sao chép kế hoạch năm | Chỉ hiển thị số cũ, không tạo dự thảo năm mới từ số cũ. | In-scope gap | Medium | `catalog/views.py:76-110,120-129`; TASKS M2-T07 `327-337` | Chốt sao chép tự động/gợi ý và đối chiếu trước xác nhận. |
| Chọn phiếu tháng | Có URL theo `ky_id` nhưng không có trang chọn kỳ; manual yêu cầu nhận URL thủ công. | In-scope gap | Medium | `entry/urls.py:33`; `entry/views.py:478-515`; manual `207-220` | Thêm trang chọn kỳ đang mở và trạng thái phiếu. |
| Ghi business data qua Admin | Seeded superuser sửa phiếu/số liệu/dự án ngoài `can()`/workflow, không tạo `LichSuXuLy`. | In-scope gap | Blocker | `seed_localhost.py:24-30`; `entry/admin.py:9-55,96-168`; `activities/admin.py:107-134`; DB `admin.is_superuser=True` | Khóa business CRUD admin hoặc áp cùng permission/workflow; không cấp superuser vận hành. |
| Khóa kỳ/sửa đồng thời | Transition có lock nhưng save nháp và kiểm tra kỳ không khóa; thiếu unique phiếu chính theo target. | In-scope gap | High | `entry/views.py:121-165,517-559`; `entry/forms.py:503-565`; `workflow.py:104-131`; `entry/models.py:93-125` | Khóa hàng/kiểm tra trạng thái trong cùng transaction; thêm unique constraint và race tests. |
| Ngưỡng django-axes | Cấu hình khóa sau 10 lần sai trong khi TASKS M1-T05 yêu cầu verify thông báo sau 5 lần. | In-scope gap | Medium | `settings.py:121-127`; `TASKS.md:200-210` | Chủ sản phẩm chốt ngưỡng, đồng bộ acceptance test và kiểm tra sau cấu hình proxy. |
| Production settings | `DEBUG=True`, key placeholder 9 ký tự, HTTPS/HSTS/secure cookies chưa bật; 6 cảnh báo deploy. | Production gap | Blocker | `settings.py:10-18,37-48,92-106`; `.env.example:1-4`; Phụ lục A | Secret manager/env, hosts/origins, HTTPS, secure cookies, HSTS; chặn production nếu key mẫu/DEBUG. |
| Media/report downloads | URL `/media/...xlsx` trả 200 không login trong cấu hình hiện tại. | Production gap | Blocker | `config/urls.py:22-23`; `settings.py:105-106`; Phụ lục B | Private storage; chỉ download qua view có scope; cấm public alias `/media/`. |
| Deploy/static/staging | Chỉ WSGI/ASGI; không production server/proxy/collectstatic/staging/migrate-rollback runbook. | Production gap | Blocker | `settings.py:70-75,101-106`; `pyproject.toml:6-15`; tech-stack `130-137` | Dựng Compose + gunicorn + PostgreSQL + Caddy theo định hướng; không dùng `runserver`. |
| Backup/restore | Không thấy lịch, retention, off-machine copy hoặc restore drill. | Production gap | Blocker | Không có artifact/runbook; tech-stack mới nêu ý định `pg_dump` nightly | Backup DB và media, retention/cảnh báo, diễn tập restore trước pilot. |
| Upload Excel | Chỉ kiểm tra hậu tố `.xlsx`; không giới hạn byte/ZIP size hay chống zip bomb. | Production gap | High | `reporting/forms.py:89-101`; `xlsx_import.py:70-88`; `reporting/views.py:947-972` | Giới hạn kích thước/request/entries/tổng giải nén/thời gian; test workbook độc hại. |
| Credential localhost | `seed_localhost` chứa mật khẩu cố định, show qua `--help`, tạo superuser và không guard môi trường. | Production gap | High | `seed_localhost.py:9-15,24-39,54-68` | Chỉ dùng local/test; xóa/revoke account mẫu; cấp initial admin one-time. |
| Logs/health/monitoring | Có logging mặc định Django nhưng không có cấu hình ứng dụng, health endpoint, error/uptime/disk monitor, alerting hay maintenance mode. | Production gap | High | `settings.py` không định nghĩa `LOGGING`; `config/urls.py:12-23` | Thêm log an toàn, health/error/uptime/disk alerts và người nhận cảnh báo. |
| Test/CI | Có 118 test pass; `accounts/tests.py`, `catalog/tests.py` rỗng; chưa CI, concurrency, upload security hoặc load tests. | Production gap | High | `manage.py test`; test files; TASKS M10-T02 `1105-1113` | Bổ sung permission/Admin/catalog/race/upload/precision tests và CI mỗi push. |
| Hiệu năng | Chưa có volume/benchmark; lists không paginate, report có per-activity queries, form TTTK lặp toàn cây lĩnh vực. | Production gap | High | `activities/views.py:103-149,263-271`; `report_data.py:241-269,435-485`; `entry/forms.py:145-151`; `phan_loai_grid.html:29-113` | Ước lượng volume, paginate/tối ưu query, autocomplete lĩnh vực, load test PostgreSQL. |
| Password/session/Axes | Validator mặc định min 8; không reset self-service/MFA/remember-me; session age mặc định; Axes 10 lần/15 phút. | Production gap | Medium | `settings.py:77-90,110-138`; TASKS M1-T05 `200-210` | Chốt policy reset/expiry/unlock; xác nhận Axes (TASKS verify 5, code 10); cấu hình IP proxy. |
| Legacy workbook | Chỉ inspect; importer chỉ preview file do ứng dụng xuất. | Production gap | Medium | `xlsx_import.py:1-2,70-74`; TASKS Q7 `1234` | Quyết định ngày cắt/import; nếu import thì mapping/đối soát/audit. |
| Tài liệu bàn giao | Có manual cán bộ; chưa thấy manual lãnh đạo/quản trị, kiến trúc, deploy/backup/restore/support. | Production gap | Medium | `doc/Huong_dan_su_dung_can_bo_nhap_lieu.md:1-5`; inventory | Runbook, manual từng vai trò, đào tạo và sign-off. |
| Retention/PII | Có history nhưng chưa thấy retention/xóa, data owner, access log hay policy PII. | Production gap | Medium | `settings.py:46-48,136-138`; `entry/models.py:176-239` | Phê duyệt quyền xem, mục đích/thời hạn lưu và quy trình xóa/export. |
| Responsive/accessibility | Chưa kiểm thử WCAG, bàn phím/reader, contrast hoặc thiết bị thực tế. | Improvement | Medium | Chưa có audit/test thiết bị | Kiểm thử với người dùng và thiết bị Trung tâm. |
| CVE/dependency | Lock versions; Django 5.2.19/axes 9.0.0 mới tại ngày review; openpyxl 3.1.5 từ 06/2024; không có full scan. | Improvement | Medium | `uv tree`; `pyproject.toml:5-15`; Phụ lục E | Bật SBOM/CVE scan; transitive CVE **chưa kiểm chứng được**. |
| Trang lỗi riêng | Không thấy handler/template 404/500/maintenance. | Improvement | Low | `config/urls.py:12-23`; inventory templates | Thêm trang lỗi tiếng Việt và quy trình bảo trì. |

## 4. Lỗ hổng so với tài liệu (Q1)

1. **Thiếu cây QĐ36/TT24 chính thức — High.** F03/Bảng 10 đòi mã/cấp/cây theo pháp quy. Model/loader có nhưng CSV là “Nhóm mẫu” và DB có 0 dòng (`fixtures/linh_vuc.csv:1-4`, `load_linh_vuc.py:25-30`). TASKS `1213,1228` xác nhận chưa có nguồn chuẩn.
2. **Thang hài lòng 1–5 không được kiểm tra — High.** Q3 ghi 1–5 (`TASKS.md:1230`); form chỉ đặt min 0 (`entry/forms.py:36-49`). Probe `TTTK-HT-HL=6` trả `is_valid=True`, nên giá trị sai vào average.
3. **Excel làm mất độ chính xác — High.** Decimal→float (`xlsx_export.py:30-35`); thử nghiệm `12345678901234.1234` đọc lại thành `12345678901234.12`. Test hiện chỉ kiểm tra cell numeric (`reporting/tests.py:777-820`).
4. **Export thiếu cấu phần báo cáo — High.** Bảng 18 yêu cầu breakdown TTTK và danh sách HTKN. Preview có dữ liệu (`report_data.py:435-538`), Excel chỉ `report.rows` (`xlsx_export.py:68-119`); Word không render breakdown, center không dùng danh sách phòng, nhiệm vụ HTKN thiếu nội dung/kết quả (`docx_export.py:42-61,85-117`; `report_templates/*.docx`).
5. **Không có màn hình chọn kỳ tháng — Medium.** UC10 yêu cầu chọn tháng, nhưng chỉ có `/phieu/thang/<ky_id>/`; manual nói cán bộ phải nhận URL thủ công (`doc/Huong_dan_su_dung_can_bo_nhap_lieu.md:207-220`).
6. **Không tạo gợi ý kế hoạch từ năm trước — Medium.** Mục 6.5 bước 1 đòi sao chép số cũ; view chỉ hiển thị số năm trước (`catalog/views.py:76-110,120-129`). TASKS M2-T07 đã kiểm tra mức thấp hơn (`TASKS.md:327-337`).
7. **Admin superuser bypass — Blocker.** Seed tạo superuser (`seed_localhost.py:24-30`); Admin business CRUD không dùng `can()`/workflow (`entry/admin.py`, `activities/admin.py`). DB hiện kiểm tra có superuser và quyền change. Có thể đổi số/status không có `LichSuXuLy`, trái Bảng 4.
8. **Race khi save/lock và phiếu trùng — High.** Workflow transition lock (`workflow.py:104-131`) nhưng `forms.save` không khóa/recheck trạng thái (`entry/forms.py:503-565`); kỳ kiểm tra trước khi lưu (`entry/views.py:517-559`). `_ensure_*_phieu` query-rồi-create, không có unique constraint phiếu chính (`entry/views.py:121-165`; `entry/models.py:93-125`).
9. **Ngưỡng Axes lệch acceptance — Medium.** `AXES_FAILURE_LIMIT=10` (`settings.py:121`) trong khi TASKS M1-T05 yêu cầu message xuất hiện sau năm lần sai (`TASKS.md:200-210`). Chốt lại yêu cầu và test lockout; không suy ra limit 5 là chính sách chính thức nếu chưa được chủ hệ thống phê duyệt.

### 4.2 Những phần có bằng chứng hoàn thành

- Bốn role và helper `can()`/`scoped()` được triển khai (`accounts/permissions.py:6-71`, `scoping.py:8-24`); test có GET/POST xuyên phòng trả 404/403. Ngoại lệ nghiêm trọng là superuser/Admin bypass.
- Workflow gửi/duyệt/trả/mở lại có transaction và lịch sử (`entry/workflow.py:51-140`); rollup official chỉ lấy `da_duyet` (`reporting/rollup.py:45-47,222-233`).
- Sáu mode rollup có entry point chung (`reporting/rollup.py:585-849`); định dạng Việt có test.
- `BaoCaoDaXuat` lưu file + snapshot, download theo scope, test hash bất biến sau reopen (`reporting/exports.py:47-92`; `reporting/views.py:408-454`; `reporting/tests.py:1029-1204`).

## 5. Lỗ hổng để đưa vào sử dụng thực tế (Q2)

### 5.1 Bảo mật

- `DEBUG=True`; key lấy từ env nhưng là placeholder; hosts chỉ localhost. `.env` không bị Git track và nằm trong `.gitignore`, nhưng `.env.example` đặt `change-me` và debug=true (`.env.example:1-4`).
- `check --deploy` phát sáu cảnh báo W004/W008/W009/W012/W016/W018. Runtime: `X_FRAME_OPTIONS=DENY` (Django default), session age 1.209.600 giây/14 ngày; `SESSION_COOKIE_SECURE=False`, `CSRF_COOKIE_SECURE=False`, trusted origins rỗng, HTTPS redirect False. Project không định nghĩa `LOGGING` tùy chỉnh.
- `/admin/` nằm trên URL công khai tiêu chuẩn; Django vẫn kiểm tra staff/superuser, nhưng chưa có IP/network restriction.
- `/media/` public trong DEBUG đã tái hiện. Upload chỉ check suffix `.xlsx`, không giới hạn kích thước/tài nguyên ZIP.
- Axes limit 10, cooloff 15 phút (`settings.py:110-134`), lệch TASKS M1-T05 verify sau 5 lần (`200-210`); reverse proxy chưa kiểm thử.
- Password validators Django mặc định, min 8 (`settings.py:77-90`); reset self-service/MFA/remember-me không có. Manual hướng dẫn liên hệ admin nhưng chưa có support procedure.
- `uv.lock` khóa dependency. Django 5.2.19 phát hành 03/11/2026 và axes 9.0.0 phát hành 30/10/2026; `openpyxl 3.1.5` phát hành 06/2024. Chưa chạy full `pip-audit`/SBOM, CVE transitive **chưa kiểm chứng được**.

### 5.2 Triển khai và vận hành

- Không có production server/proxy, static/media storage config, staging, migrate/release/rollback pipeline. Tech-stack nêu hướng Compose+gunicorn+PostgreSQL+Caddy và `pg_dump` nightly ở dòng 130–137 nhưng chưa có runbook.
- Chưa có quyết định yêu cầu zero-downtime hay maintenance window cho migration; hiện chưa có deploy procedure để biết thời gian ngừng dịch vụ.
- Không thấy backup schedule/retention/off-machine/restore drill. RPO/RTO **chưa kiểm chứng được**; file báo cáo cũng cần backup nhất quán.
- Có logging mặc định Django ra handler mặc định, nhưng không có cấu hình ứng dụng/structured log, health/error/uptime/disk monitoring, alerting, maintenance mode hay custom 404/500. PostgreSQL 17 chỉ kiểm tra ở localhost; chưa có production DB/pool/tuning.

### 5.3 Chất lượng và kiểm thử

- Không phải 0 test: 118 `test_*` và toàn suite pass trong 32.287 giây trên PostgreSQL test DB.
- `accounts/tests.py` và `catalog/tests.py` chỉ docstring; chưa CI, matrix role×URL/Admin, race, zip bomb, production headers hoặc load gần thực tế. TASKS M10-T02 ghi kiểm tra thủ công trong session notes (`1105-1113`).
- `ruff`, Django check, migration check sạch; chưa thấy type-checker/code review process.
- `rollup`/workflow có docstrings/type hints tại business entry points; không có type-check CI hoặc quy trình review/branch protection được kiểm chứng.

### 5.4 Dữ liệu

- DB localhost: `PhongBan=4`, `NhomChiTieu=18`, `ChiTieu=96`, `BieuMauChiTieu=81`, `NguonSoLieu=10`, `ChiTieuKeHoach=26`, `KyBaoCao=1`, `HoatDong=4`, `DuAn=0`, `PhieuNhapLieu=3`, `SoLieu=9`, `LichSuXuLy=7`, `BaoCaoDaXuat=2`, `BaoCaoDaXuatDong=10`, `DanhMucLinhVuc=0`. Đây là DB dev nhỏ.
- Seed indicators/form khá rộng, nhưng field tree chính thức vắng mặt. Kế hoạch HTKN mặc định trống; cần người nghiệp vụ giao/xác nhận. 26 dòng hiện có không chứng minh kế hoạch đầy đủ hoặc đã ký.
- `SoLieu.gia_tri=Decimal(18,4)` (`entry/models.py:260-265`), timezone đúng `Asia/Ho_Chi_Minh`, `USE_TZ=True` (`settings.py:92-99`). DB constraint chỉ cấm dòng có đồng thời đối tượng+lĩnh vực; chưa cấm âm/sai phòng. Admin/superuser bypass UI.
- Chỉ lưu kỳ tháng (`catalog/models.py:474-533`); legacy `.xlsx` chỉ inspect, importer chỉ preview export của app (`xlsx_import.py:1-2,70-74`); không có importer legacy `.docx`.
- Chưa có volume forecast/index/query benchmark. Rollup nhiều aggregation; center report chạy rollup theo từng phòng (`report_data.py:141-148`); activity gaps có truy vấn theo từng activity (`241-269,435-458`). Activity/project lists chưa paginate; form TTTK render toàn cây lĩnh vực trong mỗi select.
- XLSX/Word được tạo đầy đủ trong `BytesIO` rồi giữ bytes trong memory (`xlsx_export.py:127-129`, `docx_export.py:120-124`, `exports.py:95-98`); chưa có export memory/load test trên kỳ lớn.

### 5.5 Sản phẩm và trải nghiệm

- UI nhìn chung tiếng Việt; static scan không thấy TODO/FIXME/stub/empty urlpatterns trong mã đang chạy; chỉ còn dòng `NotImplementedError` lịch sử trong `TASKS.md:66`. Scan tìm thấy tham chiếu cho 24/24 template HTML. Cán bộ không khám phá được phiếu tháng từ menu; hướng dẫn nói nhận URL thủ công.
- Có validation/error states; không thấy loading indicator (`hx-indicator`/spinner/loading) trong templates; chưa kiểm tra accessibility/keyboard/contrast trên thiết bị thật. Notification chỉ dashboard/queue/gap list; cần người kiểm tra đều đặn.
- Không có self-service reset password; chưa xác định SLA/escalation. Manual hiện chỉ cho cán bộ nhập liệu, chưa có tài liệu lãnh đạo/quản trị.

### 5.6 Quản trị và bàn giao

- Không thấy README/architecture/deploy/backup-restore/support runbook trong `solieu/`; chưa xác định release/rollback owner.
- Chưa thấy data owner từng phòng, quy trình ký nhận số cuối kỳ, retention lịch sử, policy PII/access log/escalation. `simple_history` không thay cho chính sách lưu trữ.

## 6. Đánh giá 13 câu hỏi mở Q1–Q13

| Câu hỏi | Mặc định đã ship | Chấp nhận cho production? | Quyết định/hành động còn cần |
|---|---|---|---|
| Q1 | Model + CSV loader; fixture 3 node QĐ36 mẫu; DB 0 node. | **Không.** | Cung cấp/ký xác nhận cây QĐ36/TT24 và phiên bản. **In-scope gap — High.** |
| Q2 | Chậm nếu % kế hoạch thấp hơn phần năm tuyến tính đã qua (`rollup.py:494-505`). | Chỉ tạm dùng ở pilot có sign-off. | Duyệt ngưỡng/năm đầu-cuối/kế hoạch điều chỉnh. **Production gap — Medium.** |
| Q3 | Điểm 1–5 average; app nhận 6. | **Không.** | Duyệt thang và thêm validation. **In-scope gap — High.** |
| Q4 | R&D nhập theo tháng, mode `latest`. | Có nếu chỉ cập nhật một lần/tháng. | Chốt nguồn/hiệu lực/có cần nhiều đợt. **Production gap — Medium.** |
| Q5 | Chỉ lưu tháng; quý/năm là range; quý đóng khi ba tháng khóa. | Có nếu không cần khóa quý riêng. | Chốt ai khóa/mở, lý do và trạng thái kỳ. **Production gap — Medium.** |
| Q6 | Word trơn, không letterhead. | **Không** cho bản phát hành chính thức. | Cung cấp và duyệt mẫu phòng/trung tâm. **Production gap — Medium.** |
| Q7 | Legacy chỉ inspect; importer preview export app. | Có nếu có ngày cắt/archive; không nếu cần lịch sử. | Chủ dữ liệu quyết định import và mapping. **Production gap — Medium.** |
| Q8 | Free text tùy chọn, giữ session đến export. | Có nếu là nhận xét định tính. | Chốt người viết/tiêu chí/bắt buộc/người duyệt. **Production gap — Low.** |
| Q9 | Badge trạng thái riêng với official approved count. | **Có**, nếu giữ nhãn tách biệt. | Ký duyệt định nghĩa/nhãn. **Improvement — Low.** |
| Q10 | Bulk approve chặn khi validation lỗi/thiếu required (`workflow.py:286-304`). | Tạm chấp nhận pilot. | Lãnh đạo định nghĩa warning nào cấm duyệt. **Production gap — Medium.** |
| Q11 | In-app only, không email/scheduler. | Chỉ pilot có người theo dõi hàng ngày. | Chỉ định người/SLA và quyết định email/reminder. **Production gap — Medium.** |
| Q12 | Seed center head vào BGĐ; model không ép role này thuộc BGĐ. | Có nếu provisioning luôn gán BGĐ. | Có ép `phong=BGĐ` không. **Improvement — Low.** |
| Q13 | Một role/User; department head bao gồm quyền nhập. | Có nếu không có kiêm nhiệm hoặc dùng hai account an toàn. | Chọn hai account hay nhiều role. **Production gap — Medium.** |

`TASKS.md:1226` yêu cầu con người trả lời trước khi task được đánh dấu hoàn thành; 83 task đã `[x]` nhưng Q1–Q13 chưa có quyết định ghi nhận.

## 7. Lộ trình tối thiểu

### Trước khi chạy thí điểm (pilot)

1. Không mở build hiện tại ra mạng thật: `DEBUG=False`, secret production, hosts/origins thật, HTTPS/secure cookies; private media; WSGI server/proxy, không `runserver`.
2. Khóa business writes qua Admin ngoài workflow; loại superuser seed; sửa save/period locking race và unique phiếu chính.
3. Backup DB **và media**, off-machine/retention; restore drill trước khi nhập dữ liệu.
4. Chốt phạm vi pilot: nếu chỉ HTKN, nhập kế hoạch được duyệt và ký ngày cắt dữ liệu; không nhận dữ liệu TTTK/GDCN phân loại trước khi cây chuẩn sẵn sàng.
5. Sửa validation 1–5, chốt precision XLSX, kiểm thử report output và duyệt mẫu Word/Excel pilot.
6. Chạy test trên staging tương đương; kiểm tra Admin/IDOR, backup/restore và người dùng HTKN ký xác nhận luồng nhập→duyệt→export.

### Trước khi dùng chính thức (production)

1. Nạp/đối soát QĐ36/TT24, kế hoạch được xác nhận và sign-off các mặc định Q2/Q4–Q8/Q10–Q13.
2. Staging, deploy/migrate/rollback, static/media storage, secrets, release tagging/changelog.
3. CI chạy Ruff/check/migration/tests; thêm permission matrix/Admin/race/upload/precision/file-authorization tests.
4. Giới hạn upload/zip bomb; health/error/uptime/disk alerts; test Axes qua proxy.
5. Volume forecast, pagination/index/query budget/load test; autocomplete lĩnh vực thay toàn cây options; tối ưu N+1 và export memory.
6. Trang chọn kỳ tháng, manual lãnh đạo/quản trị, đào tạo ba phòng, support/reset-password/on-call.
7. Phê duyệt retention/PII/audit, ký mẫu báo cáo, chỉ định data owner và quy trình chốt số cuối kỳ.

## 8. Ước lượng công sức và rủi ro

| Hạng mục | Effort | Rủi ro nếu bỏ qua |
|---|---:|---|
| Production settings/HTTPS/secrets/Admin roles | L | Chiếm tài khoản, lộ session, ghi số trái phép. |
| Private media + backup/restore drill | M | Lộ báo cáo hoặc mất dữ liệu không phục hồi. |
| Admin/workflow/period locking + DB constraints | L | Sửa số không audit, phiếu trùng/ghi sau khóa. |
| Cây QĐ36/TT24 + kế hoạch | M nếu có CSV chuẩn; XL nếu phải thu thập | Không nhập được hoặc báo cáo phân loại sai. |
| Đối chiếu catalog 3 phòng + sign-off | M | Thiếu/sai chỉ tiêu, nguồn, biểu mẫu hoặc số kế hoạch dù seed chạy được. |
| Validation hài lòng + tests | S | Bình quân sai nhưng được chấp nhận. |
| Excel precision + Word/Excel layout | M | Làm tròn số/thiếu bảng trình ký. |
| Trang chọn kỳ + sao chép kế hoạch năm trước | M | Cán bộ không tìm được phiếu; phải lập lại kế hoạch thủ công/sai. |
| Upload protections | M | DoS qua workbook. |
| CI/test permission/race/security | M | Lỗi hồi quy phát hiện sau khi số thật bị ảnh hưởng. |
| Staging/deploy/rollback/monitoring | L | Sự cố deploy kéo dài, không phát hiện/khôi phục. |
| Pagination/N+1/index/load test | L | Chậm/hết memory khi dữ liệu tăng. |
| Runbook/manual/đào tạo/support | M | Sai thao tác, không rõ trách nhiệm chốt kỳ. |
| Retention/PII/access policy | M | Lưu quá hạn/không đáp ứng kiểm toán. |
| Quyết định Q2/Q4–Q8/Q10–Q13 và mẫu chính thức | M; XL nếu phát sinh yêu cầu nhập legacy | Mặc định chưa được chủ nghiệp vụ phê duyệt sẽ thành quy tắc báo cáo sai. |

## 9. Câu hỏi cần quyết định

1. Ai cung cấp/ký xác nhận QĐ36/TT24 và chịu trách nhiệm khi danh mục đổi?
2. Pilot từ kỳ nào; có import lịch sử không; kế hoạch HTKN năm nào đã được duyệt?
3. Excel có cần giữ chính xác số tiền/số trên 15 chữ số có nghĩa không; định dạng nào được chấp nhận?
4. Ai được sửa phiếu đã duyệt/kỳ khóa; có chặn business CRUD qua admin không?
5. Ai duyệt Q2/Q4/Q5/Q6/Q8/Q10 và mẫu báo cáo?
6. Q7: import legacy hay ký ngày cắt/archive gốc ở đâu?
7. Q11: ai xem gap list mỗi ngày; có email/reminder không?
8. Q13: có người kiêm nhiệm không; hai account hay nhiều role?
9. Ai là data owner, người reset tài khoản/trực sự cố, người duyệt retention và RPO/RTO?
10. Hạ tầng/domain/provider nào; ai quản trị PostgreSQL/media/TLS và chi phí?

## 10. Phụ lục bằng chứng

### A. Output lệnh

- `uv run ruff check .` → `All checks passed!`
- `uv run python manage.py check` → `System check identified no issues (0 silenced).`
- `uv run python manage.py check --deploy` → 6 warnings: `security.W004` HSTS; `W008` HTTPS redirect; `W009` key yếu; `W012` session cookie secure; `W016` CSRF cookie secure; `W018` DEBUG. `System check identified 6 issues (0 silenced).`
- `uv run python manage.py makemigrations --check --dry-run` → `No changes detected`.
- `uv tree --depth 1` → `django 5.2.19`, `django-axes 9.0.0`, `django-environ 0.14.0`, `django-htmx 1.29.0`, `django-simple-history 3.13.0`, `docxtpl 0.20.2`, `openpyxl 3.1.5`, `psycopg[binary] 3.3.8`, `ruff 0.17.4 (group: dev)`.
- `uv run python manage.py test` → `Ran 118 tests in 32.287s`, `OK`, `Found 118 test(s)`. Test runner tạo/hủy test database riêng.

### B. Cấu hình, file và probe

- `DEBUG=True`; `SECRET_KEY_LENGTH=9`, placeholder=True (không ghi giá trị key); `ALLOWED_HOSTS=['localhost','127.0.0.1']`.
- `.env` không tracked, nằm trong `.gitignore`; `MEDIA_URL=/media/`, `MEDIA_ROOT` tồn tại.
- Django test client chưa đăng nhập: `GET /media/bao-cao/2026/11/HTKN_thang-11-2026_20261112-181219-908925_52f007.xlsx` → HTTP 200. Đây là localhost với DEBUG, không phải domain production.
- `DanhMucLinhVuc` DB count 0; fixture có 3 dòng sample QĐ36. `TTTK-HT-HL=6`: `ActivityEntryForm.is_valid() == True`. Excel round-trip `12345678901234.1234` → `12345678901234.12`.

### C. Ma trận quyền suy ra từ `accounts/permissions.py`

`P` = theo phòng, `T` = toàn trung tâm, `—` = từ chối; `department_head` bao gồm quyền nhập trong phòng.

| Hành động | Cán bộ nhập liệu | Lãnh đạo phòng | Lãnh đạo Trung tâm | Quản trị hệ thống |
|---|---|---|---|---|
| Sửa/gửi phiếu | P | P | — | — |
| Duyệt/trả/mở lại | — | P | — | — |
| Xem danh mục | — | P | — | T |
| Xác nhận kế hoạch | — | P | — | — |
| Quản lý user/catalog/kỳ | — | — | — | T |
| Tiến độ/lịch sử | P | P | T | T |
| Báo cáo phòng | P | P | T theo phòng | T theo phòng |
| Báo cáo trung tâm | — | — | T | T |
| Admin business CRUD | — | — | — | **Superuser ghi ngoài matrix/workflow** |

Bằng chứng: `accounts/permissions.py:6-49`, `scoping.py:8-24`; ngoại lệ `seed_localhost.py:24-30`, `entry/admin.py`, `activities/admin.py`. Các view chính đã spot-check scope/can; không thấy IDOR trực tiếp trong các route thường, nhưng Admin superuser bypass là ngoại lệ.

### D. Số bản ghi DB localhost

| Model | Count | Model | Count |
|---|---:|---|---:|
| PhongBan | 4 | ChiTieu | 96 |
| NhomChiTieu | 18 | BieuMauChiTieu | 81 |
| DanhMucDoiTuong | 5 | DanhMucLinhVuc | 0 |
| NguonSoLieu | 10 | LoaiHoatDong | 13 |
| ChiTieuKeHoach | 26 | KyBaoCao | 1 |
| HoatDong | 4 | DuAn | 0 |
| PhieuNhapLieu | 3 | SoLieu | 9 |
| HoTroDuAn | 0 | LichSuXuLy | 7 |
| BaoCaoDaXuat | 2 | BaoCaoDaXuatDong | 10 |

Đây là DB dev; không dùng để suy ra volume production.

### E. Truy vết chính

- Settings/media: `config/settings.py:10-18,37-48,70-106,110-138`; `config/urls.py:22-23`.
- Permission: `apps/accounts/permissions.py:6-71`; `apps/accounts/scoping.py:8-24`.
- Catalog: `apps/catalog/models.py:286-327,412-533`; `apps/catalog/seed_data.py:29-75,188-222,663-681`; `fixtures/linh_vuc.csv:1-4`.
- Workflow/concurrency: `apps/entry/models.py:93-125,241-310`; `apps/entry/views.py:121-165,478-559`; `apps/entry/workflow.py:81-140`; `apps/entry/forms.py:36-49,309-342,503-565`.
- Rollup/export/performance: `apps/reporting/rollup.py:222-233,494-511,585-849`; `xlsx_export.py:30-35,68-129`; `docx_export.py:23-124`; `report_data.py:141-148,199-269,435-538`.
- Tests/task claims: `activities/tests.py` (15), `entry/tests.py` (48), `reporting/tests.py` (55); `accounts/tests.py`/`catalog/tests.py` (0); `TASKS.md:1105-1113,1164-1240`.
- Django security release 03/11/2026: <https://www.djangoproject.com/weblog/2026/nov/03/security-releases/>. `openpyxl 3.1.5`: <https://pypi.org/project/openpyxl/3.1.5/>. Đây không phải full CVE scan.
