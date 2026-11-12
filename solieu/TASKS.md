# solieu — implementation plan

Status: draft for approval. Do not start feature work until this plan is accepted.

Checkbox convention: mark a task `[x]` only after its **Verify** steps have been done on localhost.

## 4.1 Overview

### Goal

Take `solieu/` from a wired Django scaffold to a localhost system that covers the requirements in `doc/Phan_tich_thiet_ke_yeu_cau_phan_mem.docx` and the decisions in `doc/Chot_lua_chon_tech_stack.md`.

An entry officer at Phòng HTKN can create a training class, fill a form generated from `BieuMauChiTieu`, and submit it. The department head approves it. The center head sees a read-only progress table and can export the period. Dashboard, Excel, and Word all call `reporting.rollup`. A downloaded file stays unchanged after the form is reopened.

### Scope

- Three departments named in the requirements: Phòng Giao dịch công nghệ (GDCN), Phòng Thông tin – Thống kê (TTTK), Phòng HTKN. Phòng HTKN is the first end-to-end pilot; GDCN and TTTK catalogs are still seeded in M2 so center-wide reports have all three sections.
- Four roles, one `role` field, department scoping through one queryset helper.
- Catalog maintained in Django admin. Data entry, approval, progress, and reports use Django templates.
- Manual verification with `runserver` at `http://127.0.0.1:8000`.

### Assumptions used so work can continue

These are the proposed defaults from section 4.6. Tasks below implement them.

- One role per user. `department_head` includes every `entry_officer` permission inside that user's department. This follows the tech-stack decision. The requirements sentence about assigning an extra role is satisfied for the only example the document gives (a department head who also enters data).
- `entry_officer` and `department_head` must have `phong_id`. `center_head` is stored on department `BGĐ` (Ban Giám đốc) and can read every department. `system_admin` may have an empty `phong`.
- `KyBaoCao` rows are monthly data-entry periods. A quarter or a year report is a date range over those months plus activity end dates and support dates. A month is locked by the system admin. A quarter is treated as closed when its three months are locked.
- Official aggregates include `Đã duyệt` phiếu only. The training-class screen may also show a separate count of activities already marked `Đã tổ chức`, including the one on screen, labeled as trạng thái hoạt động.
- `cach_tong_hop = count` counts activities of the linked `LoaiHoatDong` that have an approved result phiếu, or distinct `DuAn` with an approved support of the linked support type. The link is stored on `ChiTieu` (`count_subject`, optional `loai_hoat_dong`, optional `loai_ho_tro`).
- `cach_tong_hop = ratio` divides the cumulative value of `chi_tieu_tu_so` by `chi_tieu_mau_so`. "Đã tổ chức/tổng số" on the progress screen is the count compared with the annual plan, which is the percent-of-plan display.
- Average is computed in Python from the approved values in the period. SQL computes sum, count, cumulative, and latest.
- Behind schedule means percent of plan is below the share of the year that has elapsed, using `Asia/Ho_Chi_Minh`. Indicators with an empty plan are "chỉ theo dõi" and have no percent and no late flag.
- `SoLieu.gia_tri` is `Decimal(18, 4)`. Screens and Word render Vietnamese grouping (`1.234`) and strip trailing zeros. Excel cells stay numeric with a number format so a spreadsheet can still sum them.
- A value must be less than or equal to another value on the same phiếu when `ChiTieu.khong_vuot_chi_tieu` points at that other indicator. Known pairs from F04 are seeded that way.
- Split rows are separate: a `SoLieu` row has an object, or a field, or neither. A row with both is invalid. Each dimension must sum to the total row before submit.
- Contract value on a Cafe công nghệ phiếu is one number for that event. The annual total is the sum of those numbers.
- "Mức độ hài lòng" is a 1–5 score, aggregated with `average`.
- R&D extraction figures ("theo đợt trích xuất") are entered on the monthly phiếu and aggregated with `latest`.
- In-app lists are the only notification. No email.
- Periods are opened and closed by the system admin. No scheduler.
- QĐ 36 and TT 24 trees are modeled, seeded with the handful of nodes named in the examples, and loaded in full only when `fixtures/linh_vuc.csv` is present.
- Published output is a new file plus normalized snapshot rows of the rollup result. Form contents are not stored as one JSON document.
- "Đánh giá hiệu quả" is an optional note typed on the department report preview and stored on the snapshot.
- Legacy workbooks in `doc/` are inspected and not loaded into approved `SoLieu`. Import that writes rows is the round-trip of an `.xlsx` this app exported.
- Word templates shipped in `report_templates/` are plain docxtpl files until the center supplies letterhead.

### Non-goals

- pytest, pytest-django, factory-boy, gunicorn, whitenoise, Docker, CI, Node, a SPA, or a public API.
- Departments outside GDCN, TTTK, and HTKN.
- Email, password self-service, and production deployment.
- An English UI.
- A fourth recording mode, a third chart, or a per-indicator database column.

### Current-state snapshot

Verified while writing this plan. The app boots. Business behavior is absent.

| Area | State |
|---|---|
| Tooling | `pyproject.toml` and `uv.lock` pin Django 5.2.19, psycopg 3, django-htmx, django-simple-history, django-axes 9, openpyxl, docxtpl, django-environ, ruff. |
| Settings | `config/settings.py` loads `.env`, PostgreSQL via `DATABASE_URL`, `LANGUAGE_CODE = "vi"`, `TIME_ZONE = "Asia/Ho_Chi_Minh"`, axes, HTMX, and history middleware. `USE_THOUSAND_SEPARATOR` is off. |
| URLs | `/` renders `templates/home.html`. `/admin/` is Vietnamese. App includes under `/accounts/`, `/catalog/`, `/activities/`, `/entry/`, `/reporting/` have empty `urlpatterns` and return 404. |
| Apps | `apps.py` is real (`name = "apps.<app>"`, Vietnamese `verbose_name`). `models.py`, `views.py`, `forms.py`, `admin.py`, and `tests.py` are one-line docstrings. Migrations are empty packages. |
| Reporting | `apps/reporting/rollup.py` defines `rollup(period, *, department_id=None)` and raises `NotImplementedError`. |
| UI shell | `templates/base.html` loads vendored Tabler 1.7.4, HTMX 2.0.11, Alpine.js 3.17.5, and ECharts 5.6.0. |
| Auth | Django's built-in user. Local superuser `admin` exists. There is no `role` or `phong_id`. Switching `AUTH_USER_MODEL` in M1 requires dropping and recreating database `solieu`. |
| Database | PostgreSQL 17, database `solieu`, ICU locale `vi-VN`, owner `solieu`, on `127.0.0.1:5432`. |
| Empty dirs | `fixtures/.gitkeep`, `report_templates/.gitkeep`. |

### URL map

Mount these from the existing app `urls.py` files. Remove the English prefixes in `config/urls.py` when M1-T05 lands. Paths stay stable for later tasks.

| Path | App | Screen |
|---|---|---|
| `/` | `config.views` | Post-login home |
| `/dang-nhap/`, `/dang-xuat/` | accounts | Session login and logout |
| `/admin/` | Django admin | Users, catalog, periods |
| `/danh-muc/` | catalog | Read-only catalog for a department head |
| `/ke-hoach/<nam>/` | catalog | Confirm the annual plan |
| `/hoat-dong/`, `/hoat-dong/tao/`, `/hoat-dong/<id>/` | activities | Activities |
| `/du-an/`, `/du-an/tao/`, `/du-an/<id>/` | activities | Projects |
| `/phieu/hoat-dong/<hoat_dong_id>/` | entry | Activity result form |
| `/phieu/thang/<ky_id>/` | entry | Monthly form |
| `/phieu/du-an/<du_an_id>/` | entry | Project support form |
| `/phieu/<id>/` | entry | Phiếu detail |
| `/duyet/` | entry | Approval queue |
| `/tien-do/` | reporting | Progress table |
| `/bao-cao/` | reporting | Report preview and export |
| `/bao-cao/da-xuat/` | reporting | Published files |
| `/lich-su/` | reporting | Search and year comparison |

### Execution order

Milestone numbers match the outcomes in section 4.2. Implement in this order, because the monthly and training-class screens display aggregates and the rollup needs `SoLieu` to exist:

`M0 → M1 → M2 → M3 → M4-T01..T03 → M6 → M4-T04..T11 → M5 → M7 → M8 → M9 → M10`

## 4.2 Milestones

| ID | Milestone | Outcome when it is done |
|---|---|---|
| M0 | Baseline verification | `check`, `migrate`, `ruff check`, and `runserver` pass on the current scaffold. |
| M1 | Accounts, roles, department scoping | Four roles log in. `scoped()` filters by `phong_id`. Department head includes entry rights. Center head is read-only across departments. |
| M2 | Catalog | Departments, indicator tree, annual plans, lookups, periods, and form templates are manageable in admin. HTKN, GDCN, and TTTK catalogs are seeded. |
| M3 | Activities | Activity types already seeded can be instantiated. Partner units, projects, and ad-hoc tasks exist. |
| M4 | Data entry | Forms are generated from `BieuMauChiTieu`. Numbers are `SoLieu` rows. Draft save works for activity, month, and project phiếu. |
| M5 | Approval workflow | Nháp → Chờ duyệt → Đã duyệt, or Trả lại, or Mở lại. Each step writes `LichSuXuLy`. |
| M6 | Reporting rollup | `reporting.rollup` implements all six modes plus percent of plan and the late flag. Execute M6 after M4 models and before M4 screens. |
| M7 | Excel and Word export | Period preview exports `.xlsx` and `.docx`. Each export creates an immutable `BaoCaoDaXuat`. |
| M8 | Dashboard and charts | Home shows drafts, returns, the approval queue, and percent complete. Progress is a table. At most two ECharts. |
| M9 | Audit and published reports | Field history and workflow comments are readable. Downloaded files stay byte-for-byte stable after reopen. Search works. |
| M10 | End-to-end verification and polish | The scenario in section 5 passes. UI strings are Vietnamese. `ruff check` and `manage.py check` pass. |

## 4.3 Tasks

### M0 — Baseline verification

- [ ] **M0-T01 — Re-run the scaffold checks**
  - **Why:** later milestones need a known-good database and a clean lint baseline.
  - **Files:** none.
  - **Depends on:** none.
  - **Requirement:** tech-stack localhost section; current scaffold.
  - **Acceptance criteria:**
    - `uv run ruff check .` exits 0.
    - `uv run python manage.py check` prints no issues.
    - `uv run python manage.py migrate` applies nothing new on the existing database.
  - **Verify:** from `solieu/`, run the three commands above.
  - **Estimate:** S

- [ ] **M0-T02 — Confirm the shell serves Vietnamese pages and vendor assets**
  - **Why:** M8 and M4 reuse `base.html`. A broken vendor path should be fixed before feature screens exist.
  - **Files:** `templates/base.html`, `templates/home.html`, `static/vendor/`.
  - **Depends on:** M0-T01.
  - **Requirement:** tech stack UI, language, and vendored assets.
  - **Acceptance criteria:**
    - `GET /` returns 200 and contains "Tổng hợp số liệu" and "Trung tâm Khởi nghiệp sáng tạo".
    - The four vendor URLs in `base.html` each return 200.
    - `GET /admin/login/` shows "Đăng nhập" and "Tên đăng nhập".
  - **Verify:** `uv run python manage.py runserver`, then open `/` and `/admin/login/` and each `/static/vendor/...` URL referenced by `base.html`.
  - **Estimate:** S

### M1 — Accounts, roles, department scoping

- [ ] **M1-T01 — Add `PhongBan`**
  - **Why:** users, indicators, and phiếu all hang off a department. The model lives in `catalog` as the tech stack assigns departments there.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M0-T01.
  - **Requirement:** mục 5.4 `PhongBan`; Bảng 1; Bảng 31.
  - **Acceptance criteria:**
    - Fields: `ma_phong`, `ten_phong`, `dang_su_dung`.
    - `ma_phong` is unique. Admin labels are Vietnamese.
    - `HistoricalRecords` is registered.
  - **Verify:** migrate, open `/admin/`, create `GDCN`, `TTTK`, `HTKN`, and `BGĐ`.
  - **Estimate:** S

- [ ] **M1-T02 — Replace the built-in user with `accounts.User`**
  - **Why:** the tech stack requires one `role` and `phong_id` on the account. The local database already migrated Django's `auth_user`, so this task recreates `solieu`.
  - **Files:** `apps/accounts/models.py`, `apps/accounts/migrations/`, `config/settings.py`.
  - **Depends on:** M1-T01.
  - **Requirement:** mục 5.4 `NguoiDung`; tech stack "một trường role và phong_id".
  - **Acceptance criteria:**
    - `AUTH_USER_MODEL = "accounts.User"`.
    - Fields: `username` (UI label "Tên đăng nhập"), `ho_ten`, `email`, `role`, nullable `phong` FK, `is_active`.
    - `role` choices: `entry_officer`, `department_head`, `center_head`, `system_admin`.
    - `HistoricalRecords` is registered. Axes still uses the username field.
    - Fresh database procedure is `dropdb solieu`, `createdb` with ICU locale `vi-VN`, then `migrate`.
  - **Verify:** recreate the database, migrate, `createsuperuser`, and in the shell confirm the user has `role` and `phong_id`. Log in at `/admin/` with that account.
  - **Estimate:** M

- [ ] **M1-T03 — Encode the permission matrix**
  - **Why:** every later view asks one module whether the role may perform the action.
  - **Files:** `apps/accounts/roles.py`, `apps/accounts/permissions.py`.
  - **Depends on:** M1-T02.
  - **Requirement:** mục 2.1; Bảng 3; Bảng 4.
  - **Acceptance criteria:**
    - `can(user, action, phong_id=None)` covers: manage users, manage catalog, view catalog, edit plan, confirm plan, view plan, manage periods, edit entry, approve entry, view progress, export a department report, export the center report, view history.
    - `department_head` is allowed every `edit_entry` action inside `user.phong_id`.
    - `center_head` is refused `edit_entry`, `approve_entry`, `manage_users`, `manage_catalog`, and `manage_periods`.
    - `entry_officer` is refused the center-report action and every admin action.
    - A scoped role is refused when `phong_id` is not their department.
  - **Verify:** from `manage.py shell`, print `can(...)` for all four roles against `edit_entry`, `approve_entry`, `export_center_report`, and `manage_users`. Compare the printout with Bảng 4.
  - **Estimate:** M

- [ ] **M1-T04 — Add the single department queryset helper**
  - **Why:** the tech stack forbids scattering department filters across views.
  - **Files:** `apps/accounts/scoping.py`.
  - **Depends on:** M1-T03.
  - **Requirement:** tech stack "lọc dữ liệu theo phòng ở một queryset helper".
  - **Acceptance criteria:**
    - `scoped(user, queryset, phong_field="phong_id")` returns the queryset unchanged for `center_head` and `system_admin`.
    - For `entry_officer` and `department_head` it filters to `user.phong_id`.
    - A scoped user with an empty `phong_id` gets an empty queryset.
    - Views still call `can()` before using the queryset. The helper does not grant write access.
  - **Verify:** in the shell, create two `PhongBan` rows, build a queryset of departments, and show that an HTKN officer receives only HTKN while the center head receives both.
  - **Estimate:** S

- [ ] **M1-T05 — Vietnamese login and logout**
  - **Why:** entry officers never use `/admin/` to sign in.
  - **Files:** `apps/accounts/views.py`, `apps/accounts/urls.py`, `apps/accounts/forms.py`, `config/urls.py`, `templates/accounts/login.html`, `templates/base.html`.
  - **Depends on:** M1-T02.
  - **Requirement:** F13; tech stack session auth.
  - **Acceptance criteria:**
    - `GET /dang-nhap/` renders a Vietnamese form. Successful login lands on `/`.
    - `POST /dang-xuat/` ends the session and returns to `/dang-nhap/`.
    - A bad password shows a Vietnamese error. Axes lockout still shows the Vietnamese cooloff message from settings.
    - App URLs are mounted at the site root using the URL map. The old `/accounts/` prefix is gone.
  - **Verify:** open `/dang-nhap/`, submit a wrong password, submit the superuser password, log out. After five failures the lockout message appears in Vietnamese.
  - **Estimate:** M

- [ ] **M1-T06 — User administration for the system admin**
  - **Why:** UC01 is an admin task, not a template screen.
  - **Files:** `apps/accounts/admin.py`, `apps/accounts/forms.py`.
  - **Depends on:** M1-T02, M1-T03.
  - **Requirement:** F13; UC01; Bảng 4 row "Quản lý người dùng".
  - **Acceptance criteria:**
    - Admin can create and deactivate a user, set `ho_ten`, `role`, and `phong`.
    - Saving an `entry_officer` or `department_head` without `phong` fails with a Vietnamese error.
    - A non-admin who reaches `/admin/` cannot change users.
  - **Verify:** as system admin, create one user of each role. Try to save an HTKN officer with an empty department and confirm the error.
  - **Estimate:** M

- [ ] **M1-T07 — Seed the localhost departments and four role users**
  - **Why:** every later manual test needs the same accounts after the database reset.
  - **Files:** `apps/accounts/management/commands/seed_localhost.py`.
  - **Depends on:** M1-T06.
  - **Requirement:** Bảng 3; Bảng 1.
  - **Acceptance criteria:**
    - The command is safe to run twice.
    - It ensures departments `GDCN`, `TTTK`, `HTKN`, `BGĐ`.
    - It ensures `cb.htkn` (entry, HTKN), `ld.htkn` (department head, HTKN), `ld.tt` (center head, BGĐ), and `admin` (system admin).
    - Dev passwords are localhost-only constants printed by `--help`.
  - **Verify:** run the command twice, then log in as each of the four users at `/dang-nhap/`.
  - **Estimate:** S

- [ ] **M1-T08 — Require login on the home page and show the signed-in role**
  - **Why:** the current home is public. Later dashboard cards replace this shell in M8.
  - **Files:** `config/views.py`, `templates/home.html`, `templates/base.html`.
  - **Depends on:** M1-T05, M1-T07.
  - **Requirement:** mục 2; tech stack post-login home.
  - **Acceptance criteria:**
    - Anonymous `GET /` redirects to `/dang-nhap/`.
    - The navbar shows `ho_ten` and the Vietnamese role name.
    - The page body has no business numbers yet.
  - **Verify:** open `/` in a private window and confirm the redirect. Log in as `cb.htkn` and as `ld.tt` and read the navbar.
  - **Estimate:** S

### M2 — Catalog

- [ ] **M2-T01 — Add `NhomChiTieu` and its admin**
  - **Why:** indicators are grouped phòng → mảng → chỉ tiêu.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M1-T01.
  - **Requirement:** F01; mục 5.4 `NhomChiTieu`.
  - **Acceptance criteria:**
    - Fields: `phong`, `ten_mang`, `thu_tu`.
    - Admin list is filtered by department and ordered by `thu_tu`.
    - `HistoricalRecords` is registered. Labels are Vietnamese.
  - **Verify:** in `/admin/`, add mảng "Lớp huấn luyện" under HTKN and confirm it appears under that department only.
  - **Estimate:** S

- [ ] **M2-T02 — Add `ChiTieu` and its admin**
  - **Why:** an indicator is a row of configuration, never a database column.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M2-T01.
  - **Requirement:** F01; mục 5.1; mục 5.4 `ChiTieu`; Bảng 21.
  - **Acceptance criteria:**
    - Fields include `ma_chi_tieu`, `ten_chi_tieu`, `don_vi_tinh`, `nhom`, `chi_tieu_cha`, `kieu_ghi_nhan` (`activity`, `month`, `project`), `cach_tong_hop` (the six modes), `chi_tieu_tu_so`, `chi_tieu_mau_so`, `phan_loai_doi_tuong`, `phan_loai_linh_vuc`, `khong_vuot_chi_tieu`, `count_subject`, optional count links, `dang_su_dung`.
    - `ma_chi_tieu` is unique. Ratio mode requires both numerator and denominator. Other modes reject those FKs.
    - Parent and child belong to the same department. `HistoricalRecords` is registered.
  - **Verify:** in admin, save a parent "Lớp huấn luyện" (`count`) and a child "Số học viên tham gia" (`sum`). Try to save a `ratio` indicator with an empty denominator and confirm the Vietnamese error.
  - **Estimate:** L

- [ ] **M2-T03 — Add shared lookup tables**
  - **Why:** object, field, and source are chosen while typing a phiếu, from catalogs the admin maintains.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M1-T01.
  - **Requirement:** F03; mục 5.4 `DanhMucDoiTuong`, `DanhMucLinhVuc`, `NguonSoLieu`.
  - **Acceptance criteria:**
    - `DanhMucDoiTuong` has `ten_doi_tuong`.
    - `DanhMucLinhVuc` has `he_thong` (`qd36` or `tt24`), `ma`, `ten`, `cap`, and nullable `cha`.
    - `NguonSoLieu` has `ten_nguon`.
    - `ChiTieu` gains an optional M2M `nguon_cho_phep`.
    - All three models register `HistoricalRecords`.
  - **Verify:** in admin, create "Doanh nghiệp", a parent/child pair under `qd36`, and source "Tại sự kiện". Attach the source to one indicator.
  - **Estimate:** M

- [ ] **M2-T04 — Add `LoaiHoatDong` and `BieuMauChiTieu`**
  - **Why:** the activity form renders exactly the rows of this table.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M2-T02.
  - **Requirement:** F03; mục 5.4 `LoaiHoatDong`, `BieuMauChiTieu`; tech stack form rule.
  - **Acceptance criteria:**
    - `LoaiHoatDong` has `phong`, `ten_loai`, `co_ke_hoach_so_luong`.
    - `BieuMauChiTieu` has `loai_hoat_dong`, `chi_tieu`, `bat_buoc`, `thu_tu`, unique together on the pair.
    - The indicator's department matches the activity type's department.
    - Admin edits the form template as an inline ordered by `thu_tu`.
  - **Verify:** create activity type "Lớp huấn luyện" for HTKN with four inline indicators. Reload the admin page and confirm the order matches `thu_tu`.
  - **Estimate:** M

- [ ] **M2-T05 — Add `DonViPhoiHop` and a merge action**
  - **Why:** F03 keeps partner units as a shared catalog. The model lives in `activities` because that app owns the relation to events.
  - **Files:** `apps/activities/models.py`, `apps/activities/admin.py`, `apps/activities/migrations/`.
  - **Depends on:** M2-T03.
  - **Requirement:** F03; mục 5.4 `DonViPhoiHop`.
  - **Acceptance criteria:**
    - Fields: `ten_don_vi`, nullable `doi_tuong`.
    - `HistoricalRecords` is registered. Admin labels are Vietnamese.
    - Admin action "Gộp đơn vị trùng" repoints relations onto the chosen keeper and deletes the duplicate. Relations do not exist yet, so the action updates FKs that are present at the time it runs.
  - **Verify:** create "Đại học A" and "Đại học A ". Run the merge action and confirm one row remains.
  - **Estimate:** M

- [ ] **M2-T06 — Add `ChiTieuKeHoach`**
  - **Why:** percent of plan and "đã tổ chức/tổng số" need a confirmed annual number. An empty value means "chỉ theo dõi".
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M2-T02, M2-T03.
  - **Requirement:** F02; UC04; mục 6.5; mục 5.4 `ChiTieuKeHoach`.
  - **Acceptance criteria:**
    - Fields: `chi_tieu`, `nam`, nullable `gia_tri_ke_hoach` (`Decimal`), nullable `doi_tuong`, `trang_thai` (`du_thao`, `da_xac_nhan`), `ly_do`.
    - Unique together on indicator, year, and object.
    - Changing a confirmed value requires `ly_do`. `HistoricalRecords` keeps the previous number.
  - **Verify:** enter HTKN "số lớp" = 6 for the current year as draft. Change it after marking it confirmed without a reason and confirm the save is rejected. Change it with a reason and open the history page in admin to see the old value.
  - **Estimate:** M

- [ ] **M2-T07 — Let the department head confirm the annual plan**
  - **Why:** UC04 gives confirmation to the department head, who does not administer the catalog.
  - **Files:** `apps/catalog/views.py`, `apps/catalog/urls.py`, `apps/catalog/forms.py`, `templates/catalog/ke_hoach.html`.
  - **Depends on:** M2-T06, M1-T03, M1-T04.
  - **Requirement:** UC04; Bảng 4 row "Nhập chỉ tiêu kế hoạch năm"; mục 6.5.
  - **Acceptance criteria:**
    - `GET /ke-hoach/<nam>/` shows the caller's department tree, last year's number, this year's draft, and the "chỉ theo dõi" mark when the value is empty.
    - Department head can confirm or return the draft with a comment. Return sets the lines back to `du_thao`.
    - Entry officer is refused. Center head can open the page read-only for any department via a department filter. System admin edits numbers in `/admin/`, not on this page.
  - **Verify:** as `admin`, save a draft for HTKN. As `ld.htkn`, open `/ke-hoach/<nam>/`, return it with a comment, then confirm it. As `cb.htkn`, the same URL responds 403.
  - **Estimate:** M

- [ ] **M2-T08 — Add monthly `KyBaoCao` open and close**
  - **Why:** monthly entry is allowed only while the month is open.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/admin.py`, `apps/catalog/migrations/`.
  - **Depends on:** M1-T03.
  - **Requirement:** UC05; mục 6.2; mục 5.4 `KyBaoCao`.
  - **Acceptance criteria:**
    - Fields: `loai_ky` fixed to `thang` for rows created here, `nam`, `so_ky`, `tu_ngay`, `den_ngay`, `trang_thai` (`mo`, `khoa`).
    - Unique together on year and month number.
    - Only `system_admin` sees the admin changelist. Opening and closing are admin actions.
  - **Verify:** as `admin`, open the current month and close the previous month. Confirm both states in the changelist.
  - **Estimate:** S

- [ ] **M2-T09 — Seed the HTKN catalog**
  - **Why:** Phòng HTKN is the pilot and its form templates must exist before M4.
  - **Files:** `apps/catalog/seed_data.py`, `apps/catalog/management/commands/seed_catalog.py`.
  - **Depends on:** M2-T04, M2-T05, M2-T06, M1-T07.
  - **Requirement:** Bảng 7; F01; F03; UC08.
  - **Acceptance criteria:**
    - The command is safe to run twice.
    - It creates HTKN groups, activity types (lớp huấn luyện, hội nghị/hội thảo, triển lãm, nhiệm vụ phát sinh), child indicators, and `BieuMauChiTieu` rows from Bảng 7.
    - Annual plan numbers are left empty ("chỉ theo dõi") because the HTKN source file has none.
    - Partner-unit types and the five named đối tượng exist.
  - **Verify:** run the command twice. In admin, open "Lớp huấn luyện" and confirm the inline indicators match Bảng 7 (học viên, chứng nhận, chuyên gia, khảo sát).
  - **Estimate:** L

- [ ] **M2-T10 — Seed GDCN and TTTK catalogs**
  - **Why:** a center report has one section per department, and the three "yêu cầu công nghệ" figures must not be one indicator.
  - **Files:** `apps/catalog/seed_data.py`, `apps/catalog/management/commands/seed_catalog.py`.
  - **Depends on:** M2-T09.
  - **Requirement:** Bảng 5; Bảng 6; mục 3.1.1 note on three technology-request indicators; F01.
  - **Acceptance criteria:**
    - GDCN activity types and monthly Techport indicators from Bảng 5 exist, including separate codes for technology requests via techport.vn, at the showcase event, and at Cafe công nghệ.
    - TTTK monthly indicators from Bảng 6 exist. "Tỷ lệ đơn công bố/đơn đã đăng ký" is `ratio` and points at the two source indicators.
    - R&D extraction indicators use `latest`. "Mức độ hài lòng" uses `average`.
    - Known ≤ pairs from F04 are stored in `khong_vuot_chi_tieu`.
  - **Verify:** run `seed_catalog`. In admin, search "yêu cầu công nghệ" and confirm three codes. Open the ratio indicator and confirm numerator and denominator.
  - **Estimate:** L

- [ ] **M2-T11 — Read-only catalog for the department head**
  - **Why:** Bảng 4 gives the department head "Xem (P)" on the catalog and does not give them admin edit rights.
  - **Files:** `apps/catalog/views.py`, `apps/catalog/urls.py`, `templates/catalog/danh_muc.html`.
  - **Depends on:** M2-T02, M1-T04.
  - **Requirement:** Bảng 4 row "Quản lý danh mục chỉ tiêu".
  - **Acceptance criteria:**
    - `GET /danh-muc/` lists groups and indicators for `scoped()` departments.
    - The page has no edit controls.
    - Entry officer receives 403. System admin is pointed at `/admin/` from the navbar later; direct access still shows every department.
  - **Verify:** as `ld.htkn`, open `/danh-muc/` and confirm GDCN indicators are absent. As `cb.htkn`, confirm 403.
  - **Estimate:** S

- [ ] **M2-T12 — Load the field-code tree when a CSV is present**
  - **Why:** QĐ 36 and TT 24 are required catalogs, and the legal code lists are not in the repository.
  - **Files:** `apps/catalog/management/commands/load_linh_vuc.py`, `fixtures/linh_vuc.csv` (optional, not invented).
  - **Depends on:** M2-T03.
  - **Requirement:** F03 danh mục lĩnh vực; mục 5.4 `DanhMucLinhVuc`.
  - **Acceptance criteria:**
    - CSV columns are `he_thong,ma,ten,cap,ma_cha`.
    - Missing file prints a Vietnamese instruction and exits 0 without deleting seeded example nodes.
    - A present file upserts by (`he_thong`, `ma`) and links parents.
  - **Verify:** run the command with no file and confirm the example nodes from M2-T03 remain. Add a three-row CSV under `fixtures/`, run again, and confirm parent and child in admin.
  - **Estimate:** M

### M3 — Activities

- [ ] **M3-T01 — Add `HoatDong` and `HoatDongDonVi`**
  - **Why:** a phiếu hangs off an activity, and the result form opens only after the activity exists.
  - **Files:** `apps/activities/models.py`, `apps/activities/admin.py`, `apps/activities/migrations/`.
  - **Depends on:** M2-T04, M2-T05.
  - **Requirement:** mục 5.4 `HoatDong`, `HoatDong_DonVi`; UC06.
  - **Acceptance criteria:**
    - `HoatDong` fields: `loai_hoat_dong`, `ten`, `tu_ngay`, `den_ngay`, `dia_diem`, `hinh_thuc` (`truc_tiep`, `truc_tuyen`, `ket_hop`), `linh_vuc`, `doi_tuong_huong_toi`, `trang_thai` (`ke_hoach`, `da_to_chuc`), `noi_dung`, `ket_qua`.
    - `den_ngay` defaults to `tu_ngay` when empty. `den_ngay` is not before `tu_ngay`.
    - `HoatDongDonVi` stores `hoat_dong`, `don_vi`, `vai_tro` text. `HistoricalRecords` is on `HoatDong`.
    - Department is derived from `loai_hoat_dong.phong`.
  - **Verify:** in the shell, create an HTKN "Lớp huấn luyện" activity in status `ke_hoach` with one partner unit. Saving `den_ngay` before `tu_ngay` fails.
  - **Estimate:** M

- [ ] **M3-T02 — Activity list and edit screens**
  - **Why:** UC06 is a template screen for the entry officer, not an admin screen.
  - **Files:** `apps/activities/views.py`, `apps/activities/forms.py`, `apps/activities/urls.py`, `templates/activities/hoat_dong_list.html`, `templates/activities/hoat_dong_form.html`.
  - **Depends on:** M3-T01, M1-T03, M1-T04.
  - **Requirement:** UC06; F04 thông tin chung; Bảng 4.
  - **Acceptance criteria:**
    - `/hoat-dong/` lists `scoped()` activities. Filters: year, type, status, name.
    - `/hoat-dong/tao/` and `/hoat-dong/<id>/` accept `edit_entry` only.
    - `center_head` can open the list and detail and receives 403 on POST.
    - The type dropdown is limited to the caller's department. Center head can filter departments.
    - Copy is Vietnamese.
  - **Verify:** as `cb.htkn`, create "Lớp khởi nghiệp tháng 11" with dates and place. As `cb` of another department, the same URL is absent from the list. As `ld.tt`, open the detail and confirm the save button is absent.
  - **Estimate:** L

- [ ] **M3-T03 — Add a partner unit from the activity form**
  - **Why:** UC02 allows the entry officer to add a unit inline. They still cannot open catalog admin.
  - **Files:** `apps/activities/views.py`, `templates/activities/don_vi_form.html`, `templates/activities/hoat_dong_form.html`.
  - **Depends on:** M3-T02, M2-T05.
  - **Requirement:** UC02; UC08 bước 2; F03.
  - **Acceptance criteria:**
    - HTMX POST creates a `DonViPhoiHop` and returns the updated checkbox list with the new unit selected.
    - The new name is stored once. A duplicate name returns the existing row.
    - `center_head` receives 403.
  - **Verify:** on `/hoat-dong/tao/`, add "Vườn ươm ABC" without leaving the page. Reload and confirm the unit is still selected. Search admin and confirm a single row.
  - **Estimate:** M

- [ ] **M3-T04 — Move an activity from Kế hoạch to Đã tổ chức**
  - **Why:** mục 6.1 bước 2 opens data entry only after this transition.
  - **Files:** `apps/activities/views.py`, `templates/activities/hoat_dong_form.html`.
  - **Depends on:** M3-T02.
  - **Requirement:** mục 6.1; F04.
  - **Acceptance criteria:**
    - The button is shown to roles with `edit_entry`.
    - POST sets `trang_thai = da_to_chuc` and records history.
    - The screen then links to `/phieu/hoat-dong/<id>/`. Until M4-T04 the link may 404; the activity status must already be `da_to_chuc`.
  - **Verify:** as `cb.htkn`, mark the class from M3-T02 as "Đã tổ chức". Refresh and confirm the status label. History in admin shows the old status.
  - **Estimate:** S

- [ ] **M3-T05 — Add `DuAn` screens**
  - **Why:** incubation support is recorded per project, not per event.
  - **Files:** `apps/activities/models.py`, `apps/activities/views.py`, `apps/activities/forms.py`, `apps/activities/urls.py`, `templates/activities/du_an_list.html`, `templates/activities/du_an_form.html`, `apps/activities/migrations/`.
  - **Depends on:** M1-T04, M2-T09.
  - **Requirement:** F06; UC11; mục 5.4 `DuAn`.
  - **Acceptance criteria:**
    - Fields: `phong`, `ten_du_an`, `chuong_trinh` (`nq20`, `nq64`, `ngoai_nq20`), `hinh_thuc` (`uom_tao`, `tang_toc`), `nam`.
    - List and form use `scoped()` and `edit_entry`. Center head is read-only.
    - `HistoricalRecords` is registered.
  - **Verify:** as `cb.htkn`, create a project "Startup A" under `nq20` / `uom_tao`. As `ld.tt`, open `/du-an/` and confirm it is visible and not editable.
  - **Estimate:** M

- [ ] **M3-T06 — Capture ad-hoc task text on the activity**
  - **Why:** F07 is a text activity, and it must not become numeric `SoLieu`.
  - **Files:** `templates/activities/hoat_dong_form.html`, `apps/activities/forms.py`.
  - **Depends on:** M3-T02, M2-T09.
  - **Requirement:** F07; UC12; Bảng 7 dòng 6.
  - **Acceptance criteria:**
    - When the type is "Nhiệm vụ phát sinh", the form shows `noi_dung` and `ket_qua` and hides numeric hints.
    - Both fields are required before status can become `da_to_chuc`.
    - Other activity types do not require those fields.
  - **Verify:** as `cb.htkn`, save a "Nhiệm vụ phát sinh" with both texts, mark it organized, and confirm the detail page shows the text.
  - **Estimate:** S

### M4 — Data-entry models

Execute these three tasks before M6. Execute M4-T04 and later after M6.

- [ ] **M4-T01 — Add `PhieuNhapLieu`**
  - **Why:** the phiếu is the unit of approval for an activity, a month, or a project.
  - **Files:** `apps/entry/models.py`, `apps/entry/admin.py`, `apps/entry/migrations/`.
  - **Depends on:** M3-T01, M3-T05, M2-T08.
  - **Requirement:** mục 5.1; mục 5.4 `PhieuNhapLieu`; Bảng 34.
  - **Acceptance criteria:**
    - Fields: `phong`, `loai_phieu` (`hoat_dong`, `thang`, `du_an`), nullable FKs `hoat_dong`, `ky`, `du_an`, `la_phieu_bo_sung`, `trang_thai` (`nhap`, `cho_duyet`, `da_duyet`, `tra_lai`), `nguoi_nhap`, `ngay_gui`.
    - A check constraint requires exactly one of the three targets, matching `loai_phieu`.
    - `phong` matches the target's department. `HistoricalRecords` is registered.
  - **Verify:** migrate. In the shell, save one activity phiếu and one monthly phiếu. Saving a row with both `hoat_dong` and `ky` set raises `IntegrityError`.
  - **Estimate:** M

- [ ] **M4-T02 — Add `SoLieu` rows**
  - **Why:** every entered number is a row: indicator, value, optional object or field, and source.
  - **Files:** `apps/entry/models.py`, `apps/entry/admin.py`, `apps/entry/migrations/`.
  - **Depends on:** M4-T01, M2-T02, M2-T03.
  - **Requirement:** mục 5.1; mục 5.4 `SoLieu`; mục 5.6; tech stack numeric storage.
  - **Acceptance criteria:**
    - Fields: `phieu`, `chi_tieu`, `gia_tri` `DecimalField(max_digits=18, decimal_places=4)` nullable, nullable `doi_tuong`, nullable `linh_vuc`, nullable `nguon`, `ghi_chu`.
    - A check constraint rejects a row that has both `doi_tuong` and `linh_vuc`.
    - `HistoricalRecords` is registered. No indicator is stored as its own column. The phiếu is not stored as JSON.
  - **Verify:** in the shell, insert a total row and an object-split row for the same indicator. Inserting a row with both classifications raises `IntegrityError`.
  - **Estimate:** M

- [ ] **M4-T03 — Add `HoTroDuAn`**
  - **Why:** project support is a dated line on a project phiếu so rollup can count distinct projects and sum experts.
  - **Files:** `apps/entry/models.py`, `apps/entry/admin.py`, `apps/entry/migrations/`.
  - **Depends on:** M4-T01, M3-T05.
  - **Requirement:** F06; UC11; mục 5.4 `HoTroDuAn`.
  - **Acceptance criteria:**
    - Fields: `du_an`, `phieu`, `loai_ho_tro` (`ngay_cong`, `chuyen_gia`, `dich_vu`, `khac`), `noi_dung`, `so_chuyen_gia` nullable decimal, `ngay_ho_tro`.
    - The phiếu is `loai_phieu = du_an` and points at the same project.
    - `HistoricalRecords` is registered.
  - **Verify:** in the shell, attach one `chuyen_gia` support line to the project from M3-T05. A support line whose phiếu points at another project fails validation.
  - **Estimate:** M

### M6 — Reporting rollup

Execute after M4-T03 and before M4-T04. Dashboard, Excel, and Word call this function only.

- [ ] **M6-T01 — Define the rollup inputs, period windows, and result rows**
  - **Why:** callers share one signature. The stub `rollup(period, *, department_id=None)` grows keyword arguments without a second aggregation API.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M4-T02, M4-T03, M2-T06, M3-T01.
  - **Requirement:** mục 6.3; mục 3.3; tech stack `reporting.rollup`.
  - **Acceptance criteria:**
    - `rollup(period, *, department_id=None, include_pending=False)` accepts `period` as a month, a quarter, or a year described by start date, end date, and year.
    - Activity rows are attributed by `den_ngay` (or `tu_ngay` when `den_ngay` is empty). Monthly rows use the phiếu's `KyBaoCao`. Support rows use `ngay_ho_tro`.
    - The result is a list of plain objects: indicator, department, period value, cumulative, plan, percent, remainder, behind flag, and breakdown lists. It is not persisted.
    - Empty input returns an empty list.
  - **Verify:** call `rollup` from the shell for the current month and HTKN. It returns a list and does not write a table.
  - **Estimate:** M

- [ ] **M6-T02 — Compute `sum` in SQL**
  - **Why:** period totals must come from approved `SoLieu` rows.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T01.
  - **Requirement:** Bảng 21 dòng "Tổng"; tech stack SQL sum.
  - **Acceptance criteria:**
    - The period value is the SQL `Sum` of `gia_tri` on approved phiếu inside the window and department.
    - Null values are ignored. A missing total is null, not zero.
    - Draft and pending phiếu are excluded when `include_pending` is false.
  - **Verify:** approve-ready shell data: two approved class sizes 10 and 15 in the month, plus a draft of 99. `rollup` for that indicator returns 25. The draft changes nothing.
  - **Estimate:** M

- [ ] **M6-T03 — Compute `count` in SQL**
  - **Why:** "số lớp" and "số dự án được hỗ trợ chuyên gia" are counts, not sums of entered numbers.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T01.
  - **Requirement:** Bảng 21 dòng "Đếm".
  - **Acceptance criteria:**
    - Activity count is a SQL count of distinct activities of the indicator's `LoaiHoatDong` whose attribution date is in the window and that have an approved, non-supplemental result phiếu.
    - Project count is a SQL count of distinct projects with an approved support line of the indicator's `loai_ho_tro` in the window.
    - Supplemental phiếu do not add another activity.
  - **Verify:** two organized classes, one with an approved phiếu and one still draft. The count indicator returns 1.
  - **Estimate:** M

- [ ] **M6-T04 — Compute `cumulative` in SQL**
  - **Why:** "tính đến thời điểm báo cáo" is the year-to-date sum through the period end.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T02.
  - **Requirement:** Bảng 21 dòng "Lũy kế"; thuật ngữ "Lũy kế".
  - **Acceptance criteria:**
    - Cumulative is the SQL sum from 1 January of the report year through `period.end`, approved rows only.
    - The period value for a `cumulative` indicator stays the in-period sum. Cumulative is a separate result field on every mode, and it is the primary reported value when `cach_tong_hop` is `cumulative`.
  - **Verify:** monthly values 10, 20, and 30 for January–March, all approved. A March rollup shows period 30 and cumulative 60.
  - **Estimate:** M

- [ ] **M6-T05 — Compute `latest` in SQL**
  - **Why:** R&D extraction figures must not be added across updates.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T01.
  - **Requirement:** Bảng 21 dòng "Mới nhất".
  - **Acceptance criteria:**
    - SQL selects the approved value with the greatest attribution date inside the window.
    - Ties use the greater phiếu id.
    - Cumulative for this mode equals that latest value, not a sum.
  - **Verify:** two approved extraction rows, 100 then 120. Rollup returns 120.
  - **Estimate:** S

- [ ] **M6-T06 — Compute ratio, average, percent of plan, remainder, and the late flag in Python**
  - **Why:** the tech stack keeps these derived figures out of SQL.
  - **Files:** `apps/reporting/rollup.py`, `config/settings.py`.
  - **Depends on:** M6-T02, M6-T03, M6-T04, M2-T06.
  - **Requirement:** Bảng 21 dòng "Tỷ lệ", "Trung bình", "% hoàn thành"; F09; F10.
  - **Acceptance criteria:**
    - Ratio is cumulative numerator divided by cumulative denominator. Denominator 0 yields null.
    - Average is the arithmetic mean of non-null approved values in the period.
    - Percent is cumulative divided by the confirmed plan times 100. An empty plan yields null percent and null remainder.
    - Remainder is plan minus cumulative.
    - Behind is true when a percent exists and is below the elapsed fraction of the year. The fraction uses `Asia/Ho_Chi_Minh`.
    - Unconfirmed plan lines are ignored.
  - **Verify:** numerator 2, denominator 4 → ratio 0.5. Scores 4 and 5 → average 4.5. Plan 10 and cumulative 6 in a year that is three-quarters elapsed → percent 60, remainder 4, behind true. An empty plan → percent null and behind false.
  - **Estimate:** L

- [ ] **M6-T07 — Break results down by object, field, and source**
  - **Why:** TTTK reports each split separately, and the splits are not crossed.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T02.
  - **Requirement:** mục 5.1 phân loại theo từng chiều; mục 6.3 bước 4; UC10.
  - **Acceptance criteria:**
    - Breakdown lists exist for `doi_tuong`, `linh_vuc` per `he_thong`, and `nguon`.
    - A total row is the row with both FKs empty. It is not the sum of the splits inside SQL; the splits are their own groups.
    - No result row combines an object and a field.
  - **Verify:** seed the Bảng 33 shape (total 120 and four object parts). Rollup returns the total and four object lines. The object lines are absent from the field list.
  - **Estimate:** M

- [ ] **M6-T08 — Keep pending figures beside official figures**
  - **Why:** UC16 lets the user look at "gồm số chờ duyệt" without mixing those numbers into the official column.
  - **Files:** `apps/reporting/rollup.py`.
  - **Depends on:** M6-T02.
  - **Requirement:** UC16 luồng phụ 2a; F08.
  - **Acceptance criteria:**
    - `include_pending=False` uses `da_duyet` only.
    - `include_pending=True` adds `cho_duyet` into `pending_period_value` and `pending_cumulative` and does not change the official fields.
  - **Verify:** approved 10 and pending 5. The official period value is 10 and the pending field is 5.
  - **Estimate:** S

- [ ] **M6-T09 — Preview rollup from the command line**
  - **Why:** the function must be checkable before the progress screen exists.
  - **Files:** `apps/reporting/management/commands/rollup_preview.py`.
  - **Depends on:** M6-T06, M6-T07.
  - **Requirement:** mục 6.3.
  - **Acceptance criteria:**
    - Arguments: year, month or quarter, optional department code.
    - Output prints indicator code, period value, cumulative, plan, percent, and behind flag in Vietnamese labels.
  - **Verify:** `uv run python manage.py rollup_preview --year <năm> --month <tháng> --phong HTKN` prints the shell cases from M6-T02 through M6-T06.
  - **Estimate:** S

### M4 — Data-entry screens

- [ ] **M4-T04 — Render an activity form from `BieuMauChiTieu`**
  - **Why:** the entry officer sees the indicators configured for that activity type.
  - **Files:** `apps/entry/forms.py`, `apps/entry/views.py`, `apps/entry/urls.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M4-T02, M2-T04, M3-T04, M6-T03, M6-T06.
  - **Requirement:** F04; UC07; UC08; tech stack form rule.
  - **Acceptance criteria:**
    - `GET /phieu/hoat-dong/<id>/` creates the primary phiếu if the activity is `da_to_chuc` and none exists.
    - Fields appear only for active `BieuMauChiTieu` rows of that type, in `thu_tu`.
    - Each numeric input posts to a `SoLieu` row. Source is a dropdown limited by `nguon_cho_phep` when that set is non-empty.
    - The page shows "Đã tổ chức/tổng số" from `rollup` for the count indicator, and a separate status count of `da_to_chuc` activities that includes the current one.
    - `center_head` can open the page read-only.
  - **Verify:** as `cb.htkn`, open the class from M3-T04. Confirm the four HTKN training fields and no GDCN field. Save học viên 20. Reload and confirm one `SoLieu` row.
  - **Estimate:** L

- [ ] **M4-T05 — Validate cross-field rules in `clean()`**
  - **Why:** F04 rules are relations between fields, so they belong on the form, not in the template.
  - **Files:** `apps/entry/forms.py`.
  - **Depends on:** M4-T04.
  - **Requirement:** F04 kiểm tra khi lưu; UC08 bước 4; UC10 bước 6.
  - **Acceptance criteria:**
    - Required `BieuMauChiTieu` rows must be filled to submit. Draft may leave them empty.
    - Values are not negative.
    - When `khong_vuot_chi_tieu` is set, this value is less than or equal to that indicator on the same phiếu.
    - Each object split and each field-system split sums to the total row. A mismatch names the difference in Vietnamese.
    - Errors render next to the fields in Vietnamese.
  - **Verify:** on the training-class form, set chứng nhận 30 and học viên 20. Submit and confirm the Vietnamese error. Set chứng nhận 10 and confirm the form saves.
  - **Estimate:** M

- [ ] **M4-T06 — Save a draft and delete a draft**
  - **Why:** UC07 allows "Lưu nháp", and Bảng 34 allows delete while the phiếu is `nhap`.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M4-T05.
  - **Requirement:** UC07 luồng phụ 6a; Bảng 34.
  - **Acceptance criteria:**
    - "Lưu nháp" keeps `trang_thai = nhap` and allows missing required fields.
    - "Xóa nháp" deletes the phiếu and its `SoLieu` rows.
    - Delete is refused unless `can(edit_entry)` and the status is `nhap` or `tra_lai`.
  - **Verify:** save a training class with only học viên filled, reload, see status "Nháp". Delete it and confirm it disappears from `/hoat-dong/<id>/`.
  - **Estimate:** S

- [ ] **M4-T07 — Add a supplemental phiếu on the same activity**
  - **Why:** survey and later contract numbers are a second phiếu, not an overwrite of the event phiếu.
  - **Files:** `apps/entry/views.py`, `apps/entry/forms.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M4-T04.
  - **Requirement:** F04 nhập bổ sung; UC07 luồng phụ 7; mục 6.1 bước 7.
  - **Acceptance criteria:**
    - "Tạo phiếu bổ sung" adds `la_phieu_bo_sung=True` on the same activity.
    - The form shows the same indicator list. Source defaults to "Phiếu khảo sát sau sự kiện" when that source exists.
    - The supplemental phiếu has its own status and does not change the primary phiếu.
  - **Verify:** from an organized Cafe công nghệ or training class, create a supplemental phiếu, enter one number, and confirm two phiếu rows in admin for that activity.
  - **Estimate:** M

- [ ] **M4-T08 — Edit object and field splits with Alpine.js**
  - **Why:** the tech stack limits Alpine to these grids.
  - **Files:** `templates/entry/phan_loai_grid.html`, `apps/entry/forms.py`, `static/vendor/alpine/alpine.min.js` (already vendored).
  - **Depends on:** M4-T02, M2-T03.
  - **Requirement:** UC10 bước 4–6; mục 5.6; tech stack Alpine.js.
  - **Acceptance criteria:**
    - Indicators with `phan_loai_doi_tuong` show one total input and one row per applicable `DanhMucDoiTuong`.
    - Indicators with `phan_loai_linh_vuc` show a row picker for `qd36` and a row picker for `tt24`. Adding a row does not reload the page.
    - Posted grids become `SoLieu` rows. The running sum is visible before submit.
    - Alpine is not used on screens that have no split grid.
  - **Verify:** build a TTTK-style indicator flagged for both splits. Add two object rows and two QĐ 36 rows in the browser without a full reload. Save and confirm the rows in admin. Submit with parts 10+10 against total 30 and confirm the Vietnamese mismatch from M4-T05.
  - **Estimate:** L

- [ ] **M4-T09 — Open the monthly phiếu for an open period**
  - **Why:** TTTK and Techport numbers are entered once per month.
  - **Files:** `apps/entry/views.py`, `apps/entry/forms.py`, `templates/entry/phieu_thang.html`.
  - **Depends on:** M4-T08, M6-T04, M2-T08, M2-T10.
  - **Requirement:** F05; UC10; mục 6.2.
  - **Acceptance criteria:**
    - `GET /phieu/thang/<ky_id>/` creates the department's monthly phiếu when the period is `mo`.
    - The form lists that department's `kieu_ghi_nhan=month` indicators.
    - Each line shows the previous month and the cumulative figure from `rollup`.
    - A locked period is read-only and says the month is closed, in Vietnamese.
    - `scoped()` limits the phiếu to the caller's department.
  - **Verify:** open the current month as admin. As `cb.htkn` or a seeded TTTK officer, enter "người dùng tin" total 120 and the Bảng 33 split. Save draft. Close the month in admin and confirm the form no longer saves.
  - **Estimate:** L

- [ ] **M4-T10 — Enter project support lines**
  - **Why:** UC11 records each support event on the project phiếu.
  - **Files:** `apps/entry/views.py`, `apps/entry/forms.py`, `templates/entry/phieu_du_an.html`.
  - **Depends on:** M4-T03, M3-T05.
  - **Requirement:** F06; UC11.
  - **Acceptance criteria:**
    - `GET /phieu/du-an/<du_an_id>/` opens the project phiếu.
    - The form posts `HoTroDuAn` lines: type, text, expert count, date.
    - `so_chuyen_gia` is not negative. Date is required.
    - Center head is read-only.
  - **Verify:** as `cb.htkn`, add a "chuyên gia" line dated today with 2 experts on "Startup A". Reload and confirm the line. `rollup_preview` count for that support type includes the project only after M5 approval; before approval it stays out of the official count.
  - **Estimate:** M

- [ ] **M4-T11 — Keep ad-hoc tasks out of `SoLieu`**
  - **Why:** F07 says the report lists the text and does not turn it into a number.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M3-T06, M4-T01.
  - **Requirement:** F07; UC12.
  - **Acceptance criteria:**
    - Opening a phiếu for "Nhiệm vụ phát sinh" shows `noi_dung` and `ket_qua` and creates no `SoLieu` rows.
    - The phiếu still uses the approval states from M5.
  - **Verify:** open the phiếu for the ad-hoc activity from M3-T06. Save. Confirm `SoLieu` count for that phiếu is 0.
  - **Estimate:** S

### M5 — Approval workflow

- [ ] **M5-T01 — Add `LichSuXuLy`**
  - **Why:** workflow comments are a separate record from field history.
  - **Files:** `apps/entry/models.py`, `apps/entry/admin.py`, `apps/entry/migrations/`.
  - **Depends on:** M4-T01.
  - **Requirement:** mục 5.4 `LichSuXuLy`; tech stack audit split.
  - **Acceptance criteria:**
    - Fields: `phieu`, `nguoi_xu_ly`, `hanh_dong` (`gui`, `duyet`, `tra_lai`, `mo_lai`), `y_kien`, `thoi_diem`.
    - `y_kien` is required for `tra_lai` and `mo_lai`.
  - **Verify:** migrate. The model is visible in admin. Creating `tra_lai` with an empty comment fails.
  - **Estimate:** S

- [ ] **M5-T02 — Submit a phiếu**
  - **Why:** only a submitted phiếu reaches the department head.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M5-T01, M4-T05.
  - **Requirement:** UC13; mục 6.1 bước 5; Bảng 34.
  - **Acceptance criteria:**
    - "Gửi duyệt" runs full `clean()`. Failure leaves the phiếu in `nhap` or `tra_lai` and shows Vietnamese errors.
    - Success sets `cho_duyet`, fills `ngay_gui`, and writes `LichSuXuLy` `gui`.
    - The actor needs `edit_entry` on that department.
  - **Verify:** submit the valid training-class phiếu as `cb.htkn`. Confirm status "Chờ duyệt" and one history row. Submit an invalid chứng nhận/học viên pair and confirm the status does not change.
  - **Estimate:** M

- [ ] **M5-T03 — Lock a phiếu that is waiting or approved**
  - **Why:** Bảng 34 says the officer cannot edit a phiếu in `cho_duyet`, and an approved phiếu is locked.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_form.html`.
  - **Depends on:** M5-T02.
  - **Requirement:** Bảng 34; F08.
  - **Acceptance criteria:**
    - GET shows the values and hides save buttons when status is `cho_duyet` or `da_duyet`.
    - POST to save returns 403 in those states.
    - `tra_lai` and `nhap` remain editable by `edit_entry`.
  - **Verify:** as `cb.htkn`, open the submitted phiếu and confirm there is no save button. POST the save URL and confirm 403.
  - **Estimate:** S

- [ ] **M5-T04 — List phiếu waiting for the department head**
  - **Why:** UC14 starts from "Phiếu chờ duyệt".
  - **Files:** `apps/entry/views.py`, `templates/entry/duyet_list.html`.
  - **Depends on:** M5-T02, M1-T04.
  - **Requirement:** UC14; F08.
  - **Acceptance criteria:**
    - `GET /duyet/` requires `approve_entry`.
    - The list is `scoped()` to `cho_duyet` and shows type, author, and submit time.
    - Entry officer and center head receive 403.
  - **Verify:** as `ld.htkn`, open `/duyet/` and see the training-class phiếu. As `cb.htkn` and `ld.tt`, the URL returns 403.
  - **Estimate:** S

- [ ] **M5-T05 — Approve a phiếu**
  - **Why:** approved rows are the only rows official rollup reads.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_detail.html`.
  - **Depends on:** M5-T04.
  - **Requirement:** UC14 luồng chính; mục 6.1 bước 6.
  - **Acceptance criteria:**
    - "Duyệt" sets `da_duyet`, writes `LichSuXuLy` `duyet`, and locks the form.
    - The detail shows the activity or period, the numbers, the source, and the previous-period rollup for that indicator.
    - The actor's department must match.
  - **Verify:** as `ld.htkn`, approve the training class. `rollup_preview` for "số lớp" increases by 1. The officer can no longer save it.
  - **Estimate:** M

- [ ] **M5-T06 — Return a phiếu with a comment**
  - **Why:** a return without a comment is invalid, and the officer must see why.
  - **Files:** `apps/entry/views.py`, `apps/entry/forms.py`, `templates/entry/phieu_detail.html`.
  - **Depends on:** M5-T04.
  - **Requirement:** UC14 luồng phụ 4a; Bảng 34.
  - **Acceptance criteria:**
    - "Trả lại" requires `y_kien`. Empty comment redisplays the form in Vietnamese.
    - Status becomes `tra_lai`. The officer can edit and submit again.
    - The comment is visible on the phiếu.
  - **Verify:** return a second phiếu with an empty comment and confirm it stays `cho_duyet`. Return it with "Sai số học viên". As `cb.htkn`, open it, see the comment, change the number, and submit again.
  - **Estimate:** M

- [ ] **M5-T07 — Reopen an approved phiếu**
  - **Why:** UC15 allows a correction and requires a trace.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_detail.html`.
  - **Depends on:** M5-T05, M5-T01.
  - **Requirement:** UC15; Bảng 34 dòng "Đã duyệt".
  - **Acceptance criteria:**
    - Only `approve_entry` can reopen.
    - `y_kien` is required. Status returns to `nhap`.
    - `LichSuXuLy` `mo_lai` stores the reason. Field history keeps the old numbers.
    - Official rollup no longer includes the phiếu until it is approved again.
  - **Verify:** reopen the approved training class with reason "Nhập thiếu chuyên gia". `rollup_preview` count drops by 1. The history row is visible on the phiếu.
  - **Estimate:** M

- [ ] **M5-T08 — Approve several clean phiếu at once**
  - **Why:** UC14 allows bulk approval only when a phiếu has no warning.
  - **Files:** `apps/entry/views.py`, `templates/entry/duyet_list.html`.
  - **Depends on:** M5-T05, M4-T05.
  - **Requirement:** UC14 luồng phụ 1a; F08 tiện ích.
  - **Acceptance criteria:**
    - The queue marks a phiếu as blocked when `clean()` would fail or a required `SoLieu` is empty.
    - POST approves only the checked phiếu that are not blocked, and only inside `scoped()`.
    - Each approved phiếu gets its own `LichSuXuLy` row.
  - **Verify:** queue one valid phiếu and one with a split mismatch. Select both. Only the valid one becomes `da_duyet`.
  - **Estimate:** M

- [ ] **M5-T09 — Show what changed since the previous submit**
  - **Why:** F08 asks the department head to compare the resubmission with the previous send.
  - **Files:** `apps/entry/views.py`, `templates/entry/phieu_detail.html`.
  - **Depends on:** M5-T06, M4-T02.
  - **Requirement:** F08 tiện ích "xem thay đổi giữa lần gửi trước và lần gửi lại".
  - **Acceptance criteria:**
    - The detail lists `SoLieu` fields whose history changed after the previous `gui` record.
    - Labels are the indicator's Vietnamese name, the old value, and the new value.
  - **Verify:** perform the return-and-resubmit from M5-T06. As `ld.htkn`, open the phiếu and see học viên old → new.
  - **Estimate:** M

### M7 — Excel and Word export

- [ ] **M7-T01 — Preview a period report from `rollup`**
  - **Why:** the user checks the figures before downloading a file.
  - **Files:** `apps/reporting/views.py`, `apps/reporting/forms.py`, `apps/reporting/urls.py`, `templates/reporting/bao_cao.html`.
  - **Depends on:** M6-T09, M1-T03.
  - **Requirement:** F11; UC17; UC18; mục 6.4.
  - **Acceptance criteria:**
    - `GET /bao-cao/` asks for month, quarter, or year, plus scope.
    - Entry officer and department head are fixed to their department. Center head and system admin can pick one department or the whole center.
    - The table columns are: Chỉ tiêu, Đơn vị tính, Kế hoạch năm, Thực hiện trong kỳ, Lũy kế, % hoàn thành, Ghi chú.
    - Every number on the table comes from `rollup`.
  - **Verify:** as `ld.htkn`, open the current month and see the approved training-class figures. As `cb.htkn`, the department picker is absent.
  - **Estimate:** L

- [ ] **M7-T02 — Show missing inputs before export**
  - **Why:** mục 6.4 lets the user wait or export with an explicit gap note.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/bao_cao.html`.
  - **Depends on:** M7-T01, M2-T08, M3-T04.
  - **Requirement:** mục 6.4 bước 2–3; UC18 luồng phụ 2a; F10 tình trạng nhập liệu.
  - **Acceptance criteria:**
    - The preview lists months in the range that have no monthly phiếu, activities `da_to_chuc` with no result phiếu, and phiếu still `cho_duyet`.
    - "Vẫn lập báo cáo" continues and the preview shows "Số liệu chưa đầy đủ" on the affected indicators.
    - No email is sent.
  - **Verify:** leave one organized HTKN activity without a phiếu. Open the quarter preview and see it listed. Choose to continue and see the gap note.
  - **Estimate:** M

- [ ] **M7-T03 — Add the department-specific sections and the effectiveness note**
  - **Why:** UC18 asks for TTTK splits and HTKN lists, and TTTK keeps a free-text effectiveness column.
  - **Files:** `templates/reporting/bao_cao.html`, `apps/reporting/views.py`.
  - **Depends on:** M7-T01, M6-T07.
  - **Requirement:** F11 loại báo cáo; Bảng 6 ghi chú "Đánh giá hiệu quả"; UC18.
  - **Acceptance criteria:**
    - TTTK scope adds object and field breakdown tables from the rollup breakdowns.
    - HTKN scope lists classes, conferences, exhibitions, supported projects, and ad-hoc tasks in the period.
    - Center scope stacks the three departments.
    - An optional "Đánh giá hiệu quả" note can be typed per indicator by a user who may export that department. It is held for the snapshot and is not a `ChiTieu`.
  - **Verify:** preview HTKN and see the class list. Preview TTTK and see the object split. Type a note and confirm it is still on the page after refresh before export (session or unsaved form is enough at this task).
  - **Estimate:** L

- [ ] **M7-T04 — Export the period table to Excel**
  - **Why:** F11 requires `.xlsx` for further calculation.
  - **Files:** `apps/reporting/xlsx_export.py`, `apps/reporting/views.py`.
  - **Depends on:** M7-T01.
  - **Requirement:** F11 xuất file; tech stack openpyxl.
  - **Acceptance criteria:**
    - The workbook has the preview columns and, for TTTK, the effectiveness note.
    - Numeric cells are numbers with an Excel number format. They are not Vietnamese digit strings.
    - The file name contains department or `toan-trung-tam`, period, and a timestamp. Each download writes a new file under a media directory ignored by git.
  - **Verify:** export the HTKN month, open the file, confirm the training-class row matches the preview, and confirm the percent cell is numeric.
  - **Estimate:** M

- [ ] **M7-T05 — Add one docxtpl template per department and one for the center**
  - **Why:** Word export fills the department template. No letterhead file was supplied.
  - **Files:** `report_templates/htkn.docx`, `report_templates/gdcn.docx`, `report_templates/tttk.docx`, `report_templates/trung_tam.docx`.
  - **Depends on:** M7-T01.
  - **Requirement:** F11; tech stack docxtpl.
  - **Acceptance criteria:**
    - Each template contains Vietnamese headings and a docxtpl row loop over `rows`.
    - Placeholders cover the preview columns. TTTK includes `danh_gia`. HTKN includes `danh_sach`.
    - Files live in `report_templates/`.
  - **Verify:** open each `.docx` and confirm the placeholders. A missing placeholder name is listed in the task notes before M7-T06 starts.
  - **Estimate:** M

- [ ] **M7-T06 — Fill the Word template**
  - **Why:** the periodic report is delivered as `.docx`.
  - **Files:** `apps/reporting/docx_export.py`, `apps/reporting/views.py`.
  - **Depends on:** M7-T03, M7-T05.
  - **Requirement:** UC18 bước 5; tech stack docxtpl.
  - **Acceptance criteria:**
    - Department scope uses that department's template. Center scope uses `trung_tam.docx`.
    - Numbers inside the document are Vietnamese-formatted strings.
    - The gap note from M7-T02 is included when the user chose to export incomplete data.
  - **Verify:** export HTKN to Word, open it, and confirm the class name and the formatted learner count. Export the center and confirm three department headings.
  - **Estimate:** M

- [ ] **M7-T07 — Store `BaoCaoDaXuat` when a file is exported**
  - **Why:** a download must remain the file that was produced, and the snapshot is the rollup result rather than a JSON copy of the form.
  - **Files:** `apps/reporting/models.py`, `apps/reporting/admin.py`, `apps/reporting/migrations/`, `apps/reporting/views.py`.
  - **Depends on:** M7-T04, M7-T06.
  - **Requirement:** mục 5.4 `BaoCao`; tech stack `BaoCaoDaXuat`.
  - **Acceptance criteria:**
    - `BaoCaoDaXuat` stores `ky` description, nullable `phong`, `nguoi_lap`, `ngay_lap`, `dinh_dang` (`xlsx` or `docx`), and the file.
    - `BaoCaoDaXuatDong` stores one row per rollup line: indicator, period value, cumulative, plan, percent, note, and breakdown label.
    - Export inserts these rows and never updates an existing file.
  - **Verify:** export twice. Admin shows two records and two files. The first file's modified time does not change on the second export.
  - **Estimate:** M

- [ ] **M7-T08 — Read an exported workbook back**
  - **Why:** the tech stack includes reading Excel, and the only stable layout is the one M7-T04 writes.
  - **Files:** `apps/reporting/xlsx_import.py`, `apps/reporting/views.py`, `templates/reporting/xlsx_import.html`.
  - **Depends on:** M7-T04.
  - **Requirement:** tech stack "Đọc file hiện có"; F11.
  - **Acceptance criteria:**
    - Upload of an `.xlsx` produced by M7-T04 shows a preview table of the same columns.
    - The preview does not write `SoLieu` and does not approve anything.
    - A file with a different header shows a Vietnamese "không đúng mẫu" error.
  - **Verify:** upload the file from M7-T04 and compare the preview to the original screen. Upload `doc/So lieu bao cao - P. HTKN.xlsx` and confirm the mismatch error.
  - **Estimate:** M

- [ ] **M7-T09 — Inspect the legacy workbooks without loading them**
  - **Why:** the two workbooks in `doc/` have no header on row 1, and the requirements do not define a cell map.
  - **Files:** `apps/reporting/management/commands/inspect_legacy_workbook.py`.
  - **Depends on:** M7-T08.
  - **Requirement:** tech stack openpyxl read; mục 1.4 căn cứ.
  - **Acceptance criteria:**
    - The command prints sheet names and the first non-empty row of each sheet for a path under `doc/`.
    - It writes no database rows.
  - **Verify:** run it on `doc/So lieu bao cao - P. HTKN.xlsx` and on the GDCN workbook. Confirm the database row counts for `SoLieu` are unchanged.
  - **Estimate:** S

### M8 — Dashboard and charts

- [ ] **M8-T01 — Replace the home page with the post-login summary**
  - **Why:** the tech stack names this as the first screen: drafts, returns, the approval queue, and percent complete by department.
  - **Files:** `config/views.py`, `templates/home.html`, `apps/reporting/rollup.py`.
  - **Depends on:** M5-T04, M6-T06, M1-T08.
  - **Requirement:** tech stack "ba màn hình làm trước" item 1; F10.
  - **Acceptance criteria:**
    - Entry officer and department head see their `nhap` and `tra_lai` phiếu.
    - Department head also sees the `cho_duyet` count, linking to `/duyet/`.
    - Center head does not see edit links. The page shows percent complete per department from `rollup` for the current year.
    - Entry officer sees percent complete for their department only.
  - **Verify:** leave one draft and one approved class. Log in as `cb.htkn`, `ld.htkn`, and `ld.tt`. Confirm each home page matches the bullets above.
  - **Estimate:** M

- [ ] **M8-T02 — Add two ECharts and no third chart**
  - **Why:** the tech stack caps charts at two. The progress screen stays a table.
  - **Files:** `templates/home.html`, `templates/base.html`.
  - **Depends on:** M8-T01.
  - **Requirement:** tech stack Apache ECharts 5; F10.
  - **Acceptance criteria:**
    - Chart 1 is a column chart of percent complete by department for center head and system admin, or by group for a department user.
    - Chart 2 is a column chart of cumulative versus plan for the indicators in the selected department. Center head defaults the second chart to HTKN and can switch department without adding a chart.
    - Both series are JSON from `rollup` in the page. The page includes no other chart library and no third `echarts.init` call.
    - "Chỉ theo dõi" indicators are omitted from the percent chart.
  - **Verify:** view source on `/` and count `echarts.init`. Open `/` as `ld.tt` and confirm two charts. Open `/tien-do/` and confirm it has no chart.
  - **Estimate:** M

- [ ] **M8-T03 — Build the progress table**
  - **Why:** F10 is a table of plan, cumulative, percent, and remainder.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/tien_do.html`.
  - **Depends on:** M6-T06, M1-T03.
  - **Requirement:** F10; UC16.
  - **Acceptance criteria:**
    - `GET /tien-do/` filters by year and department within `can(view_progress)` and `scoped()`.
    - Rows are grouped phòng → mảng → chỉ tiêu and show plan, cumulative, percent, remainder.
    - "Chỉ theo dõi" shows the cumulative number and an em dash for percent.
    - Behind-schedule rows are visually marked. The page is a table.
  - **Verify:** as `ld.tt`, open `/tien-do/`, select the current year, and find the HTKN class count. Compare it with `rollup_preview`.
  - **Estimate:** M

- [ ] **M8-T04 — Toggle pending numbers on the progress table**
  - **Why:** UC16 keeps unaudited numbers visible and separate.
  - **Files:** `templates/reporting/tien_do.html`, `apps/reporting/views.py`.
  - **Depends on:** M8-T03, M6-T08.
  - **Requirement:** UC16 luồng phụ 2a.
  - **Acceptance criteria:**
    - The switch "Gồm số chờ duyệt" adds a column from `pending_cumulative`.
    - The official cumulative column does not change when the switch is on.
  - **Verify:** with one pending phiếu of 5 and approved 10, toggle the switch and confirm the official column stays 10.
  - **Estimate:** S

- [ ] **M8-T05 — Drill from an indicator to the phiếu that produced it**
  - **Why:** UC16 bước 5 asks for the activities behind a number.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/tien_do_chi_tiet.html`.
  - **Depends on:** M8-T03.
  - **Requirement:** UC16 bước 5.
  - **Acceptance criteria:**
    - The link lists approved activities, monthly phiếu, or support lines that `rollup` counted for that indicator and year.
    - The list is `scoped()`.
  - **Verify:** from the HTKN class-count row, open the drill and see the approved class. A draft class is absent.
  - **Estimate:** M

### M9 — Audit and published reports

- [ ] **M9-T01 — Show field history on a phiếu**
  - **Why:** simple-history answers who changed which field. The workflow table does not.
  - **Files:** `apps/entry/views.py`, `templates/entry/lich_su_truong.html`.
  - **Depends on:** M4-T02, M5-T07.
  - **Requirement:** F12; tech stack django-simple-history.
  - **Acceptance criteria:**
    - A user with `view_history` can open the history of a phiếu they may scope to.
    - Each row shows time, user, field label in Vietnamese, old value, and new value.
  - **Verify:** after the reopen-and-edit in M5-T07, open the history and see the user `cb.htkn` on the changed learner count.
  - **Estimate:** M

- [ ] **M9-T02 — Show the workflow timeline to every role that may search**
  - **Why:** F12 includes who submitted, who approved, and the comment, for readers who cannot approve.
  - **Files:** `templates/entry/phieu_detail.html`, `apps/entry/views.py`.
  - **Depends on:** M5-T01, M1-T03.
  - **Requirement:** F12; UC19.
  - **Acceptance criteria:**
    - The timeline lists `LichSuXuLy` in time order with Vietnamese action names.
    - `center_head` can read it for every department. An entry officer can read it inside their department.
  - **Verify:** as `ld.tt`, open the training-class phiếu and read the submit, return, and reopen comments.
  - **Estimate:** S

- [ ] **M9-T03 — List published files and download the original**
  - **Why:** UC18 says the stored report can be opened again.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/da_xuat.html`.
  - **Depends on:** M7-T07, M1-T04.
  - **Requirement:** UC18 kết quả; mục 5.4 `BaoCao`.
  - **Acceptance criteria:**
    - `GET /bao-cao/da-xuat/` lists period, scope, author, time, and format within `scoped()`.
    - Download returns the stored file, not a fresh export.
  - **Verify:** download the first HTKN file from the list and confirm the bytes match the file on disk.
  - **Estimate:** S

- [ ] **M9-T04 — Prove a published file survives reopen**
  - **Why:** this is the tech-stack rule that dashboard numbers are live and downloaded files are not.
  - **Files:** `apps/reporting/views.py` (only if the download regenerates a file; then stop that).
  - **Depends on:** M9-T03, M5-T07.
  - **Requirement:** tech stack `BaoCaoDaXuat`.
  - **Acceptance criteria:**
    - After reopen and a changed approved value, `GET` of the old download is byte-identical to the original file.
    - `/` and `/tien-do/` show the new approved number.
    - The snapshot rows of the old `BaoCaoDaXuat` are unchanged.
  - **Verify:** record the SHA-256 of the exported file, reopen, change học viên, approve again, download the old record, and compare the hash. Then compare `/tien-do/` with the new value.
  - **Estimate:** S

- [ ] **M9-T05 — Search activities, phiếu, and numbers**
  - **Why:** UC19 is the lookup screen for every role, inside that role's scope.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/lich_su.html`.
  - **Depends on:** M3-T02, M4-T01, M1-T04.
  - **Requirement:** F12; UC19.
  - **Acceptance criteria:**
    - Filters: year, period, department, activity type, name, partner unit, field.
    - Results include activities and phiếu. Department filters outside `scoped()` return nothing.
    - Each phiếu links to its workflow timeline.
  - **Verify:** search the class name as `cb.htkn` and find it. Search a GDCN name as `cb.htkn` and get no rows. As `ld.tt`, the GDCN row is visible if one exists.
  - **Estimate:** M

- [ ] **M9-T06 — Compare the same period across two years**
  - **Why:** F12 asks for a same-period comparison between years.
  - **Files:** `apps/reporting/views.py`, `templates/reporting/lich_su.html`.
  - **Depends on:** M6-T06, M9-T05.
  - **Requirement:** F12 "So sánh số liệu cùng kỳ giữa các năm".
  - **Acceptance criteria:**
    - The page calls `rollup` twice, once per year, for the same month or quarter and scope.
    - The table shows indicator, year A, year B, and the difference.
  - **Verify:** with data in two years, open the comparison for March and confirm both columns match `rollup_preview` for those years.
  - **Estimate:** M

### M10 — End-to-end verification and polish

- [ ] **M10-T01 — Build the navbar from the permission matrix**
  - **Why:** a role should see only the screens Bảng 4 allows.
  - **Files:** `templates/base.html`, `apps/accounts/permissions.py`.
  - **Depends on:** M8-T01, M7-T01, M5-T04, M3-T02.
  - **Requirement:** Bảng 4.
  - **Acceptance criteria:**
    - Links: Trang chủ, Hoạt động, Dự án, Duyệt, Tiến độ, Báo cáo, Lịch sử, Danh mục, Quản trị.
    - Each link is rendered only when `can()` allows it.
    - Labels are Vietnamese.
  - **Verify:** log in as each of the four seeded users and compare the visible links with Bảng 4.
  - **Estimate:** S

- [ ] **M10-T02 — Walk every URL as every role**
  - **Why:** a hidden link is not enough; POST endpoints must enforce the same matrix.
  - **Files:** the view modules already created.
  - **Depends on:** M10-T01.
  - **Requirement:** Bảng 4; tech stack authorization.
  - **Acceptance criteria:**
    - For each path in the URL map, the four roles get the response Bảng 4 implies: 200 within scope, 403 outside it.
    - A department user cannot read another department by changing an id in the URL.
  - **Verify:** record a 4-by-N grid in the session notes while clicking. Any 500 or cross-department leak is fixed before this task is checked.
  - **Estimate:** M

- [ ] **M10-T03 — Check Vietnamese number formatting on screen and in both exports**
  - **Why:** stored values stay numeric, and the reader sees `1.234`.
  - **Files:** `apps/reporting/formatting.py`, `apps/reporting/templatetags/vi_numbers.py`, templates that print decimals, `apps/reporting/xlsx_export.py`, `apps/reporting/docx_export.py`.
  - **Depends on:** M7-T06, M8-T03.
  - **Requirement:** tech stack numeric storage and `1.234` display.
  - **Acceptance criteria:**
    - A template filter renders 1234 as `1.234` and 1200.5 as `1.200,5`.
    - Database values remain `numeric`. `USE_THOUSAND_SEPARATOR` stays off so form posts are not rewritten.
    - Excel cells remain numbers. Word shows the formatted text.
  - **Verify:** enter 1200 learners or a Techport figure of 200000, approve it, and compare the progress page, the `.docx`, and the `.xlsx`.
  - **Estimate:** M

- [ ] **M10-T04 — Remove English UI copy**
  - **Why:** the tech stack requires a Vietnamese interface.
  - **Files:** `templates/`, `apps/*/admin.py`.
  - **Depends on:** M10-T01.
  - **Requirement:** tech stack "Không làm giao diện tiếng Anh".
  - **Acceptance criteria:**
    - Visible labels, buttons, empty states, and validation errors are Vietnamese.
    - Admin `verbose_name` and field labels used by staff are Vietnamese.
    - Code identifiers, URL names, and model field names stay English.
  - **Verify:** click the HTKN path from login through export and note any English string. Check `/admin/` changelist titles for the new models.
  - **Estimate:** M

- [ ] **M10-T05 — Leave ruff and Django system checks clean**
  - **Why:** the scaffold's quality bar still applies after the features land.
  - **Files:** the Python modules touched above.
  - **Depends on:** M10-T04.
  - **Requirement:** tech stack ruff; Django `check`.
  - **Acceptance criteria:**
    - `uv run ruff check .` exits 0.
    - `uv run python manage.py check` exits 0.
    - No pytest, Docker, Node, or extra direct dependency has been added.
  - **Verify:** run both commands. `uv tree --depth 1` still lists only the approved direct packages.
  - **Estimate:** S

- [ ] **M10-T06 — Run the full localhost scenario**
  - **Why:** this is the project-level definition of done.
  - **Files:** none.
  - **Depends on:** M10-T02, M10-T03, M10-T05, M9-T04.
  - **Requirement:** the whole requirements document, exercised through the scenario in section 5.
  - **Acceptance criteria:**
    - Every step in section 5 has been performed on a fresh database.
    - Failures are fixed in the owning task and this task is re-run.
  - **Verify:** follow section 5 from step 1 through step 8.
  - **Estimate:** L

## 4.4 Coverage checklist

| Required item | Tasks |
|---|---|
| Custom user with `role` and `phong_id` | M1-T02 |
| Four roles and Bảng 4 | M1-T03, M1-T06, M10-T01, M10-T02 |
| One queryset helper | M1-T04 |
| Department, indicator, plan, lookup, and form-template admin | M1-T01, M2-T01, M2-T02, M2-T03, M2-T04, M2-T06, M2-T08 |
| Activities and projects | M3-T01, M3-T02, M3-T05, M3-T06 |
| Forms generated from `BieuMauChiTieu` | M4-T04 |
| `SoLieu` rows, not columns and not form JSON | M4-T02 |
| Approval lifecycle and `LichSuXuLy` | M5-T01 through M5-T07 |
| `reporting.rollup` with six modes | M6-T02 through M6-T06 |
| SQL aggregates and Python ratio, percent, late flag | M6-T02, M6-T03, M6-T04, M6-T05, M6-T06 |
| Excel read and Excel period export | M7-T04, M7-T08, M7-T09 |
| Word export from the department template | M7-T05, M7-T06 |
| Post-login home | M8-T01 |
| Progress table and at most two charts | M8-T02, M8-T03 |
| django-simple-history on editable models | M1-T01, M1-T02, M2-T01, M2-T02, M2-T03, M2-T05, M2-T06, M3-T01, M3-T05, M4-T01, M4-T02, M4-T03, M9-T01 |
| `BaoCaoDaXuat` file plus row snapshot | M7-T07, M9-T03, M9-T04 |
| Vietnamese UI, English identifiers | M10-T04 |
| Numeric storage and `1.234` display | M4-T02, M10-T03 |
| Vendor assets in `base.html` | M0-T02 |
| Ruff and `manage.py check` | M0-T01, M10-T05 |

## 4.5 Traceability matrix

| Requirement | Tasks | Notes |
|---|---|---|
| Mục 1.3 phạm vi ba phòng | M2-T09, M2-T10 | Other departments are out of scope. |
| Mục 2, Bảng 3, Bảng 4 | M1-T02, M1-T03, M10-T02 | Single role field is the tech-stack reading of "gán thêm vai trò". |
| F01, UC03 | M2-T01, M2-T02, M2-T04, M2-T10 | |
| F02, UC04, mục 6.5 | M2-T06, M2-T07 | |
| F03, UC02 | M2-T03, M2-T05, M2-T12, M3-T03 | Full legal code lists are missing. See Q1. |
| F04, UC06, UC07, UC08, UC09, mục 6.1 | M3-T02, M3-T04, M4-T04, M4-T05, M4-T07 | |
| F05, UC10, mục 6.2 | M2-T08, M4-T08, M4-T09 | |
| F06, UC11 | M3-T05, M4-T03, M4-T10 | |
| F07, UC12 | M3-T06, M4-T11 | |
| F08, UC13, UC14, UC15, Bảng 34 | M5-T02 through M5-T09 | |
| F09, mục 3.3, Bảng 21, mục 6.3 | M6-T01 through M6-T09 | |
| F10, UC16 | M8-T01, M8-T03, M8-T04, M8-T05 | Late-flag threshold is Q2. |
| F11, UC17, UC18, mục 6.4 | M7-T01 through M7-T07 | Templates are placeholders. See Q6. |
| F12, UC19 | M9-T01, M9-T02, M9-T05, M9-T06 | |
| F13, UC01, UC05 | M1-T06, M2-T08 | |
| Mục 5.1, 5.4, 5.5, 5.6 | M4-T02, M6-T07 | Entity `BaoCao` is implemented as `BaoCaoDaXuat`. |
| Tech-stack screens to build first | M8-T01, M4-T04, M7-T01, M7-T04 | HTKN training class is the pilot form. |

### Requirements that are ambiguous or missing

- QĐ 36 / TT 24 code lists are named and not supplied (Q1).
- The late threshold is an example, not a decision (Q2).
- The satisfaction scale is unnamed (Q3).
- "Theo đợt trích xuất" is outside the three recording modes (Q4).
- Whether a quarter is its own lockable `KyBaoCao` is unspecified (Q5).
- No Word letterhead and no cell map for the legacy workbooks (Q6, Q7).
- "Đánh giá hiệu quả" has an empty column in the source file (Q8).
- The form badge "đã tổ chức/tổng số" may or may not include an unapproved activity (Q9).
- Bulk-approval "không có cảnh báo" is not defined as a list of warnings (Q10).
- "Nhận thông báo" and "gửi nhắc" have no channel (Q11).

## 4.6 Open questions

Each question has a default so implementation can continue. A human answer replaces the default before the owning task is marked done.

1. **Q1 — Where is the full QĐ 36 and TT 24 code list?** Default: ship the tree model, seed the example nodes, and load `fixtures/linh_vuc.csv` when someone drops it in. Owning task: M2-T12.
2. **Q2 — What percent counts as behind schedule?** Default: linear year elapsed in `Asia/Ho_Chi_Minh`. The quý III / 75% example matches this. Owning task: M6-T06.
3. **Q3 — What is the scale for "mức độ hài lòng"?** Default: a decimal from 1 to 5, aggregated with `average`. Owning task: M2-T10.
4. **Q4 — How is "theo đợt trích xuất" recorded?** Default: a monthly `SoLieu` row with `cach_tong_hop = latest`. No fourth phiếu type. Owning task: M2-T10.
5. **Q5 — Are quarter and year periods stored rows?** Default: only months are `KyBaoCao` rows. Quarter and year are report ranges. A quarter is closed when its three months are closed. Owning task: M2-T08.
6. **Q6 — Which `.docx` letterhead should export use?** Default: plain templates in `report_templates/` with the preview columns. Replace the files later without changing the context keys. Owning task: M7-T05.
7. **Q7 — Should the legacy HTKN and GDCN workbooks be imported as numbers?** Default: no. Their first rows are empty and no cell map was specified. `inspect_legacy_workbook` only prints structure. The writable import reads this app's own export. Owning task: M7-T09.
8. **Q8 — Who writes "Đánh giá hiệu quả", and against what criteria?** Default: optional free text on the department preview, stored on the snapshot, with no scoring rule. Owning task: M7-T03.
9. **Q9 — Does the on-form "đã tổ chức/tổng số" include an activity that is not yet approved?** Default: the badge counts activities in `da_to_chuc`, including the current one. The official rollup count includes only activities with an approved result phiếu. Both numbers are labeled. Owning task: M4-T04.
10. **Q10 — Which warnings block bulk approval?** Default: a phiếu is blocked when `clean()` fails or a required indicator is empty. Owning task: M5-T08.
11. **Q11 — What is a "thông báo" or a reminder?** Default: the home page and the gap list. No email and no background scheduler. Owning tasks: M8-T01, M7-T02.
12. **Q12 — Where does the center head sit in `PhongBan`?** Default: department `BGĐ`, and `scoped()` ignores `phong` for `center_head` and `system_admin`. Owning task: M1-T04.
13. **Q13 — May one person hold two roles?** Default: no. `department_head` already includes data entry. A person who must both lead the center and enter data needs a product decision. Owning task: M1-T03.

## 5. Definition of done

Run this on a fresh local database after M10-T05 is green.

1. Recreate the database and boot the app.
   ```bash
   dropdb solieu
   createdb solieu --owner=solieu --encoding=UTF8 --locale-provider=icu --icu-locale=vi-VN --template=template0
   cd solieu
   uv run python manage.py migrate
   uv run python manage.py seed_localhost
   uv run python manage.py seed_catalog
   uv run python manage.py runserver
   ```
2. As `admin`, confirm departments GDCN, TTTK, and HTKN, the HTKN "Lớp huấn luyện" form template, an open month, and a confirmed annual plan for the class-count indicator (enter 6 if the seed left it empty).
3. As `cb.htkn`, create activity "Lớp huấn luyện" with name, dates, place, and a new partner unit. Mark it "Đã tổ chức". Fill the generated form with học viên greater than or equal to chứng nhận and khảo sát. Save a draft, then submit.
4. As `ld.htkn`, approve it. As `ld.tt`, open the phiếu read-only and read `LichSuXuLy`. As `admin`, open field history and see who changed which value.
5. As `ld.htkn` and `ld.tt`, open `/`. Drafts, returned phiếu, the approval queue, and percent complete match the approved class. `/tien-do/` shows the class count against the plan. The home page has two charts. The progress page has none.
6. Export the HTKN month to `.xlsx` and `.docx`. Open both. The class figures match the preview. Word shows `1.234`-style grouping. Excel cells are still numbers.
7. Reopen the phiếu, change học viên, and approve again. The previously downloaded file hash is unchanged. `/tien-do/` shows the new number.
8. `uv run ruff check .` and `uv run python manage.py check` both exit 0.

## Task counts

| Milestone | Tasks |
|---|---|
| M0 | 2 |
| M1 | 8 |
| M2 | 12 |
| M3 | 6 |
| M4 | 11 |
| M5 | 9 |
| M6 | 9 |
| M7 | 9 |
| M8 | 5 |
| M9 | 6 |
| M10 | 6 |
| **Total** | **83** |
