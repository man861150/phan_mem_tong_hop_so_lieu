# Improvement tasks (localhost)

**Status:** draft for approval. No application code has been changed for this plan.

**Date:** 13 November 2026. Source review: `PRODUCTION_READINESS_REVIEW.md` (12 November 2026).

**Scope:** localhost development only. The app stays on `runserver` at `localhost` / `127.0.0.1`. Tasks are manual acceptance checks: browser, `runserver`, `manage.py shell`, `manage.py check`, and `ruff`.

## How this relates to `TASKS.md`

`TASKS.md` M0–M10 are complete (83 tasks, all `[x]`). This file is the follow-up list. Do not edit `TASKS.md`, and do not re-open a checked milestone to restate work it already required.

Q1–Q13 in `TASKS.md` §4.6 still have no recorded human answer. Where this plan implements a shipped default (satisfaction 1–5, reopen-with-comment, in-app notices), it enforces that default. Where a different answer would change behavior, the item is under **Blocked on decision**.

## Excluded

Do not add work for any of the following. The review mentioned them; they are listed again under **Deferred**.

- Automated testing: pytest, pytest-django, factory-boy, unit, integration, race, or load tests, coverage, CI.
- Deployment: gunicorn or uvicorn, reverse proxy, Docker or Compose, staging, static or media serving, `collectstatic`, release and rollback, environment parity.
- Operations: backup and restore, `pg_dump` schedules, monitoring, health checks, uptime or disk alerts, log aggregation, maintenance mode.
- Network-exposure hardening: HTTPS or HSTS, secure cookies, `SECRET_KEY` rotation, secret managers, real-domain `ALLOWED_HOSTS` or `CSRF_TRUSTED_ORIGINS`, turning `DEBUG` off for production, Axes behind a proxy.
- Governance and documentation deliverables: PII or retention policy, access-log policy, runbooks, user manuals, training, support or SLA, data-owner sign-off.
- Dependency CVE scanning and SBOM.

## Baseline for this draft

Read-only, on 13 November 2026:

- `uv run python manage.py check` — no issues.
- `uv run ruff check .` — all checks passed.
- `DanhMucLinhVuc.objects.count()` — `0`.
- `PhieuNhapLieu` — 3 rows, no duplicate primary phiếu.
- `ChiTieu` `TTTK-HT-HL` exists (`average`, object split, field split) and has no min/max field.
- Openpyxl read-back of `Decimal("12345678901234.1234")` is `12345678901234.12`, matching review appendix B. `Decimal(str(float(...)))` alone is `12345678901234.123`, so the file writer loses one more digit than `float` by itself.

Appendix D's other table counts were not re-counted.

## Priority tiers

| Tier | Meaning |
|---|---|
| **P0 — Correctness** | Wrong numbers, duplicate phiếu, writes that skip the workflow, exports that store a different number. |
| **P1 — Missing features** | Behavior the requirements and `TASKS.md` describe, which the screens or files do not do yet. |
| **P2 — Usability** | Finding a screen, lists, empty states, labels, keyboard use. |
| **P3 — Polish** | Small robustness and performance limits that matter on one machine. |

Estimates: **S** about half a day, **M** one to two days, **L** three to five days, for one person who already knows this repo.

## Already addressed

These review sentences are stale against the current code. They do not get a task.

- Center **indicator** tables already stack GDCN, TTTK, and HTKN. `apps/reporting/xlsx_export.py` writes one `PHÒNG …` section per report, and `report_templates/trung_tam.docx` loops `{%tr for phong in departments %}`. What is still missing is the TTTK breakdown and the HTKN lists (IMP-06).
- The HTKN Word template already loops `danh_sach` (name, type, time, status). It does not carry `noi_dung` / `ket_qua`, and the center template does not include that list (IMP-06).
- `LichSuXuLy` admin is already add/change/delete locked (`apps/entry/admin.py` `has_add_permission` / `has_change_permission` / `has_delete_permission`).
- Search results, published-file history, and phiếu field history are already paginated (`SEARCH_PAGE_SIZE` 25, `PUBLISHED_PAGE_SIZE` 50, `HISTORY_PAGE_SIZE` 50). Activity and project lists are not (IMP-10).
- Submit already saves inside `workflow._transition`'s `select_for_update` (`apps/entry/views.py` `_submit_entry_form`, `apps/entry/workflow.py`). Draft save, delete, and the period read sit outside that lock (IMP-03).
- Word numbers go through `format_vi_number` as text. The precision loss is the Excel numeric cell (IMP-05).

---

## P0 — Correctness

- [x] **IMP-01 — Stop business writes through `/admin/`**
  - **Priority:** P0
  - **Why:** the seeded superuser can change phiếu status, numbers, activities, and projects without `can()` and without `LichSuXuLy`. Rollup then treats those numbers as official.
  - **Evidence:** `apps/accounts/management/commands/seed_localhost.py` users tuple (`admin` is `is_superuser=True`); `apps/entry/admin.py` `PhieuNhapLieuAdmin`, `SoLieuAdmin`, `HoTroDuAnAdmin` (no permission override); `apps/activities/admin.py` `HoatDongAdmin`, `DuAnAdmin`. Catalog admins already call `can()` via `CatalogPermissionMixin`. Review §3 row "Ghi business data qua Admin", §4 item 7.
  - **Files:** `apps/entry/admin.py`, `apps/activities/admin.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - `PhieuNhapLieu`, `SoLieu`, `HoTroDuAn`, `HoatDong`, and `DuAn` return false from `has_add_permission`, `has_change_permission`, and `has_delete_permission` for every user, including a superuser. Do not call `ModelAdmin`'s implementation first; that one returns true for superusers.
    - Changelist and simple-history pages stay readable (`has_view_permission` stays true for the system admin). The `HoatDongDonVi` inline is read-only with its parent.
    - `LichSuXuLy` stays immutable. `DonViPhoiHop` and its merge action stay editable. Catalog, users, and `KyBaoCao` open/close stay editable. That is the M2-T08 and M1-T06 path.
    - Leave `seed_localhost` creating `admin` as a superuser. M1-T07 requires that account for catalog and user admin. The lock is on the five business models.
  - **Verify (localhost):** as `admin`, open each of the five changelists and confirm there is no add, save, or delete. Open a phiếu history page and confirm it still loads. Change an HTKN indicator label in catalog admin and confirm that save still works. Approve a phiếu in the app as `ld.htkn` and confirm `LichSuXuLy` gained a row.
  - **Estimate:** S

- [x] **IMP-02 — One primary phiếu per target**
  - **Priority:** P0
  - **Why:** `_ensure_activity_phieu`, `_ensure_month_phieu`, and `_ensure_project_phieu` read then insert. Two requests can both see no row. Sum and activity-count rollups add every matching approved phiếu, so a second primary doubles the figure.
  - **Evidence:** `apps/entry/views.py` `_ensure_activity_phieu`, `_ensure_month_phieu`, `_ensure_project_phieu`; `apps/entry/models.py` `PhieuNhapLieu.Meta.constraints` (type check only); `apps/reporting/rollup.py` `_sum_map` and `_activity_count_queryset` (`la_phieu_bo_sung=False` still counts every primary). Review §3 row "Khóa kỳ/sửa đồng thời", §4 item 8. This database currently has 3 phiếu and no duplicate primary.
  - **Files:** `apps/entry/models.py`, `apps/entry/migrations/`, `apps/entry/views.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - Partial unique constraints, one each: activity primary on `hoat_dong` where `loai_phieu` is hoạt động and `la_phieu_bo_sung` is false; month primary on (`phong`, `ky`) where `loai_phieu` is tháng and `la_phieu_bo_sung` is false; project primary on `du_an` where `loai_phieu` is dự án and `la_phieu_bo_sung` is false.
    - Supplemental phiếu stay unlimited.
    - Each `_ensure_*` catches `IntegrityError`, then loads the primary that won the race. The user sees that phiếu, not a 500.
    - If a migration finds existing duplicate primaries, it stops with a Vietnamese command error naming the ids. It does not delete số liệu.
  - **Verify (localhost):** `manage.py migrate` applies on this database. In `manage.py shell`, insert a second primary month phiếu for the same phòng and kỳ and confirm `IntegrityError`. Create a supplemental activity phiếu in the browser and confirm the primary is unchanged. `manage.py check` and `ruff check .` exit 0.
  - **Estimate:** M

- [x] **IMP-03 — Re-check the period and the phiếu inside the write**
  - **Priority:** P0
  - **Why:** draft save reads `KyBaoCao.trang_thai` and `PhieuNhapLieu.trang_thai`, then writes in a later transaction that does not lock either row. A close or an approval that commits in between is stored anyway. Submit locks the phiếu and still uses the earlier period read.
  - **Evidence:** `apps/entry/views.py` `phieu_thang` (period flag, then `form.save` on the draft branch), `phieu_hoat_dong` draft branch, `phieu_du_an` `form.save`, `phieu_xoa`; `apps/entry/forms.py` `IndicatorEntryForm.save`; `apps/entry/workflow.py` `_transition` (locks the phiếu only). Review §4 item 8.
  - **Files:** `apps/entry/views.py`, `apps/entry/forms.py`, `apps/entry/workflow.py`
  - **Depends on:** IMP-02
  - **Acceptance criteria:**
    - Monthly draft save, monthly submit, and monthly delete run in one transaction that `select_for_update`s the `KyBaoCao` and then the phiếu. If the period is `khoa`, or the phiếu is not `nhap` or `tra_lai`, the transaction writes nothing.
    - The refused save shows the existing sentence "Kỳ đã đóng. Phiếu tháng chỉ được xem, không được lưu." A refused save after approval shows "Phiếu đã được xử lý. Tải lại trang trước khi lưu."
    - Activity and project draft save, ad-hoc `noi_dung` / `ket_qua` save, and delete take the same phiếu lock and the same status refusal. Activity phiếu are not tied to `KyBaoCao`; do not invent that link.
    - Lock order is period, then phiếu, so an admin close and a save cannot deadlock each other.
    - Who may reopen an approved phiếu stays the department head plus a comment. That policy is blocked below.
  - **Verify (localhost):** open a month as `cb.htkn`. In another `manage.py shell`, lock that `KyBaoCao`, set `khoa`, and hold the transaction. Submit the open form and confirm it waits, then shows the closed-period sentence and leaves `SoLieu` unchanged. Release the shell, reopen the month, save `4`, and confirm the row. Repeat with the phiếu moved to `da_duyet` under a lock and confirm the draft save does not change `gia_tri`.
  - **Estimate:** M

- [x] **IMP-04 — Enforce each indicator's own min and max**
  - **Priority:** P0
  - **Why:** "Mức độ hài lòng" is specified as 1–5 and aggregated with `average`. The form only rejects negatives, so `6` is stored and moves the average.
  - **Evidence:** `apps/entry/forms.py` `_number_field` (`min_value` is 0, no `max_value`) and `_parse_field_rows` (rejects `value < 0` only). `clean()` at the split checks does not add a scale rule. `apps/catalog/seed_data.py` `_ct("TTTK-HT-HL", …)` sets `CachTongHop.AVERAGE` and `KieuGhiNhan.ACTIVITY`. `ChiTieu` has no bounds field (`apps/catalog/models.py`). `TASKS.md` Q3. Review §4 item 2. No hội thảo activity exists locally, so the form probe was not re-run; the field definition accepts any non-negative `Decimal(18, 4)`.
  - **Files:** `apps/catalog/models.py`, `apps/catalog/migrations/`, `apps/catalog/admin.py`, `apps/catalog/seed_data.py`, `apps/entry/forms.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - `ChiTieu` gains nullable `gia_tri_toi_thieu` and `gia_tri_toi_da` (`Decimal`, same 18 digits and 4 places as `SoLieu.gia_tri`). The form reads those fields. It does not branch on `ma_chi_tieu`.
    - When a bound is set, the total, each object part, and each field-split value must sit inside it. Blank stays allowed on draft. The message is "Giá trị phải từ {min} đến {max}." using the indicator's own bounds. A single bound checks only that side. Indicators with both bounds empty keep today's rule, "Giá trị không được âm."
    - `seed_catalog` writes `1` and `5` onto `TTTK-HT-HL` through `_scalar`, so a second run updates the existing row. The indicator stays an activity indicator on "Hội thảo xu hướng công nghệ".
    - Admin shows the two fields on `ChiTieu`. Existing out-of-range rows are left in place until the next save of that phiếu, which then rejects them.
  - **Verify (localhost):** `seed_catalog`. Open a TTTK hội thảo phiếu as an entry officer, enter `6` on "Mức độ hài lòng", and confirm the Vietnamese message on the total and on an object part. Enter `4`, save, approve as `ld.htkn`, and confirm `rollup_preview` shows `4` for that indicator. `manage.py check` and `ruff check .` exit 0.
  - **Estimate:** S

- [x] **IMP-05 — Reject Excel values the numeric cell cannot store**
  - **Priority:** P0
  - **Why:** `SoLieu.gia_tri` is `Decimal(18, 4)`. The workbook writes a binary float. `12345678901234.1234` is stored as `12345678901234.12`. Passing a `Decimal` into the cell does the same thing, because openpyxl persists a float.
  - **Evidence:** `apps/reporting/xlsx_export.py` `_number` and the numeric columns; `apps/entry/models.py` `SoLieu.gia_tri`. Local probe on 13 November 2026: openpyxl read-back of that decimal is `12345678901234.12`. `123456789012.1234` survives; `1234567890123.1234` becomes `1234567890123.123`. Review §4 item 3. Word export is unaffected.
  - **Files:** `apps/reporting/xlsx_export.py`, `apps/reporting/views.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - The gate is an in-memory openpyxl round trip, quantized to 4 decimal places. A cell is written only when that read-back matches the original. This is the ceiling: about 15 significant digits, judged by the file rather than by counting digits, because 16-digit `123456789012.1234` survived and 17-digit `1234567890123.1234` did not.
    - On the first failure, write no file and create no `BaoCaoDaXuat`. The preview shows "Không xuất được vì số {value} của chỉ tiêu {name} không giữ được trong ô Excel (ô sẽ lưu {stored})."
    - Cells that pass stay numeric with the current `#,##0.##` display format. Do not switch them to text. M7-T04 requires numbers.
    - Keeping all 18 digits in the file is a blocked product choice. This task rejects the export.
  - **Verify (localhost):** export a normal HTKN month and confirm the training-class cell is still numeric and matches the preview. In `manage.py shell`, call the gate on `Decimal("12345678901234.1234")` and confirm it reports `12345678901234.12` and does not return a workbook. Call it on `Decimal("123456789012.1234")` and confirm it passes. `ruff check .` exits 0.
  - **Estimate:** S

---

## P1 — Missing features

- [x] **IMP-06 — Put the preview's TTTK breakdown and HTKN lists into Excel and Word**
  - **Priority:** P1
  - **Why:** the on-screen report shows TTTK object and field breakdowns, and HTKN activities and supported projects. Excel writes only indicator rows. Word renders breakdowns nowhere, and the center document stops after the indicator tables. Ad-hoc `noi_dung` and `ket_qua` are stored on the activity and never reach the list.
  - **Evidence:** `templates/reporting/bao_cao.html` (TTTK breakdown card, HTKN activity and project tables); `apps/reporting/report_data.py` `breakdown_rows`, `activities_for_department` (no `noi_dung` or `ket_qua`); `apps/reporting/xlsx_export.py` (indicator rows only); `apps/reporting/docx_export.py` `_danh_sach`; `report_templates/tttk.docx`, `htkn.docx`, `trung_tam.docx`. Review §4 item 4. Indicator stacking itself is already in place; see **Already addressed**.
  - **Files:** `apps/reporting/report_data.py`, `apps/reporting/xlsx_export.py`, `apps/reporting/docx_export.py`, `report_templates/tttk.docx`, `report_templates/htkn.docx`, `report_templates/trung_tam.docx`, `templates/reporting/bao_cao.html`
  - **Depends on:** IMP-05
  - **Acceptance criteria:**
    - For an activity whose type is "Nhiệm vụ phát sinh", the preview, Excel, and Word show `noi_dung` and `ket_qua`. Other activity rows leave those cells blank.
    - TTTK breakdowns from `breakdown_rows` appear in the TTTK Word file, in the center Word file under TTTK, and in the workbook on a sheet after "Báo cáo". GDCN and HTKN do not gain an empty breakdown section.
    - HTKN activity and project lists appear in the HTKN Word file (extend the existing `danh_sach` loop), in the center Word file under HTKN, and on their own Excel sheet.
    - The first sheet stays "Báo cáo" with today's headers, so the existing importer still previews indicator rows only. New numeric cells go through the IMP-05 gate.
    - `gdcn.docx` stays as it is.
  - **Verify (localhost):** approve one TTTK hội thảo phiếu with an object split, and one HTKN "Nhiệm vụ phát sinh" with nội dung and kết quả. Preview TTTK and HTKN, export `.xlsx` and `.docx`, and confirm the same names and figures, including the two ad-hoc texts. Export the center and confirm three department headings plus the TTTK breakdown and the HTKN list. Upload the workbook on the import screen and confirm the preview is still the indicator table. `ruff check .` exits 0.
  - **Estimate:** L

- [x] **IMP-07 — Let the user pick an open month**
  - **Priority:** P1
  - **Why:** monthly entry exists only at `/phieu/thang/<ky_id>/`. Nothing in the navbar links there, so an officer needs a hand-built URL.
  - **Evidence:** `apps/entry/urls.py` (only the `ky_id` route); `apps/accounts/context_processors.py` `navigation` (no month item); `TASKS.md` M4-T09. Review §4 item 5.
  - **Files:** `apps/entry/urls.py`, `apps/entry/views.py`, `templates/entry/phieu_thang_chon.html`, `apps/accounts/context_processors.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - `GET /phieu/thang/` lists `KyBaoCao` rows, open months first. Each row shows tháng/năm, "Kỳ đang mở" or "Kỳ đã đóng", and, for a scoped user, the phiếu status or "Chưa có phiếu".
    - The link target stays `/phieu/thang/<ky_id>/`. Creating the phiếu stays on that page, and only while the period is open and the user may edit. Unscoped users still pick a phòng on the existing page.
    - Navbar label "Phiếu tháng" is visible to anyone who may `edit_entry` or `view_progress`.
    - No periods shows "Chưa có kỳ báo cáo. Quản trị hệ thống mở kỳ trong trang quản trị." The page does not create a `KyBaoCao`.
  - **Verify (localhost):** as `cb.htkn`, open "Phiếu tháng" from the navbar, open the current month, and save a draft. As `ld.tt`, open the same list and reach a read-only phiếu after choosing a phòng. Close the month in admin and confirm the list says "Kỳ đã đóng" and the form does not save.
  - **Estimate:** M

- [x] **IMP-08 — Copy last year's plan into this year's draft**
  - **Priority:** P1
  - **Why:** the confirmation screen shows last year's number and has no action that creates this year's draft from it. The head would retype every line.
  - **Evidence:** `apps/catalog/views.py` `_plan_lines` and `ke_hoach` (actions are only `xac_nhan` and `tra_lai`); `templates/catalog/ke_hoach.html`. `TASKS.md` M2-T07 checked the display and the confirm/return actions. Review §4 item 6. Unique key is already (`chi_tieu`, `nam`, `doi_tuong`) with `nulls_distinct=False`.
  - **Files:** `apps/catalog/views.py`, `templates/catalog/ke_hoach.html`
  - **Depends on:** —
  - **Acceptance criteria:**
    - Department head sees "Sao chép số năm trước vào dự thảo" on `/ke-hoach/<nam>/`. Posting it creates `du_thao` rows for that năm and that phòng, copied from the previous năm, including `doi_tuong`.
    - Copy only rows whose `gia_tri_ke_hoach` is not null. Skip any indicator/object that already has a row for this năm, confirmed or draft. Do not confirm the new rows.
    - A second click reports how many were created and how many were skipped, and inserts nothing new.
    - No previous numbers shows "Năm trước chưa có số kế hoạch để sao chép." System admin and center head do not see the button. Admin keeps editing plans in `/admin/`.
  - **Verify (localhost):** as `admin`, set one confirmed HTKN number for năm N−1. As `ld.htkn`, open `/ke-hoach/N/`, copy, and confirm the line is "Dự thảo" with the same number. Copy again and confirm the count does not grow. Confirm the year, then copy again and confirm the confirmed value is unchanged.
  - **Estimate:** M

- [x] **IMP-09 — Make field-tree loading visible, and show an empty state**
  - **Priority:** P1
  - **Why:** the loader and the admin changelist exist, the sample CSV has three QĐ 36 rows, and the database has zero `DanhMucLinhVuc` rows. An entry form with `phan_loai_linh_vuc` renders an empty select and does not say why. Official codes are a human decision; loading whatever file is present should still be obvious and safe to repeat.
  - **Evidence:** `fixtures/linh_vuc.csv` (header plus `MAU`, `MAU-01`, `MAU-02`); `apps/catalog/management/commands/load_linh_vuc.py` (upsert by hệ thống + mã, no delete); `apps/catalog/admin.py` `DanhMucLinhVucAdmin` (no load control). Count on 13 November 2026 is 0. M2-T03 added the model only; it does not seed nodes. Review §4 item 1, Q1.
  - **Files:** `apps/catalog/admin.py`, `apps/catalog/management/commands/load_linh_vuc.py`, `templates/entry/phan_loai_grid.html`, `apps/entry/forms.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - The `DanhMucLinhVuc` changelist shows "Nạp từ fixtures/linh_vuc.csv" even when the table is empty. A row action is not enough, because an empty table has nothing to select. The button calls the existing loader.
    - The result message counts created, updated, and unchanged rows, and always ends with "Kiểm tra lại với danh mục đã được ký trước khi nhập số liệu chính thức." A missing file shows the command's current instruction and deletes nothing. Rows absent from the CSV are left in place.
    - When a hệ thống has no rows, the field grid shows "Chưa có mã lĩnh vực QĐ 36." or "Chưa có mã lĩnh vực TT 24." plus "Quản trị hệ thống nạp file tại Danh mục lĩnh vực." It does not render a silent empty select for that hệ thống.
    - Do not add official codes in this task. The three-row sample may be loaded to prove the button, and the message above stays on screen.
  - **Verify (localhost):** as `cb.htkn` or a TTTK officer, open a hội thảo phiếu and read the empty-state sentence. As `admin`, run the button twice and confirm the changelist stays at 3 rows with parent `MAU` on the two children. Remove the CSV temporarily, run again, and confirm the instruction and the 3 rows remain. Restore the file. `ruff check .` exits 0.
  - **Estimate:** M

---

## P2 — Usability

- [x] **IMP-10 — Paginate activity and project lists**
  - **Priority:** P2
  - **Why:** both lists render every row. Search already pages at 25.
  - **Evidence:** `apps/activities/views.py` `hoat_dong_list`, `du_an_list`; `templates/activities/hoat_dong_list.html`, `templates/activities/du_an_list.html`. Review §3 row "Hiệu năng", §5.4.
  - **Files:** `apps/activities/views.py`, `templates/activities/hoat_dong_list.html`, `templates/activities/du_an_list.html`
  - **Depends on:** —
  - **Acceptance criteria:**
    - Page size is 25, same as `SEARCH_PAGE_SIZE`. Page links keep the current filters (phòng, năm, loại, trạng thái, tên).
    - The footer says "Trang {n} / {m}" when there is more than one page. The existing empty sentences stay: "Không có hoạt động phù hợp." and "Chưa có dự án."
  - **Verify (localhost):** with the seeded activities, the list shows one page and no pager. In `manage.py shell`, the paginator for a queryset longer than 25 reports 25 per page. Click a second page in the browser if you add rows, and confirm the năm filter is still selected.
  - **Estimate:** S

- [x] **IMP-11 — Search the field tree instead of repeating it in every select**
  - **Priority:** P2
  - **Why:** each indicator with `phan_loai_linh_vuc` loads every `DanhMucLinhVuc` row, and each QĐ 36 or TT 24 row, including the add-row template, repeats that full `<option>` list.
  - **Evidence:** `apps/entry/forms.py` `_add_fields` (`DanhMucLinhVuc.objects.all()`); `templates/entry/phan_loai_grid.html` selects and the two `<template>` blocks. Review §5.4, §5.5.
  - **Files:** `apps/entry/forms.py`, `apps/entry/views.py`, `apps/entry/urls.py`, `templates/entry/phan_loai_grid.html`
  - **Depends on:** IMP-09
  - **Acceptance criteria:**
    - The grid posts the same names as today (`linh_vuc_<chi_tieu_id>`, `gia_tri_lv_<chi_tieu_id>`), so `IndicatorEntryForm` validation stays the parser it already has.
    - A search field queries one endpoint by `he_thong` and `q`, returns at most 20 matches, and does not embed the whole tree in the page. Adding a row does not reload the page.
    - Zero rows for a hệ thống keeps the IMP-09 sentence. A query with no matches shows "Không tìm thấy mã lĩnh vực."
    - The endpoint requires login and returns codes only. It does not filter by phòng, because the tree is shared.
  - **Verify (localhost):** after IMP-09 has loaded the sample, open a hội thảo phiếu, type "mẫu", pick `MAU-01`, enter a value that matches the total, and save. View source and confirm the option list is not repeated once per indicator. `ruff check .` exits 0.
  - **Estimate:** M

- [x] **IMP-12 — Show a spinner on the HTMX post**
  - **Priority:** P2
  - **Why:** "Thêm đơn vị" posts with HTMX and the button gives no feedback while the request runs. That is the only `hx-post` in the templates.
  - **Evidence:** `templates/activities/hoat_dong_form.html` partner-unit button (`hx-post`, no `hx-indicator`). Review §5.5.
  - **Files:** `templates/activities/hoat_dong_form.html`
  - **Depends on:** —
  - **Acceptance criteria:**
    - The button sets `hx-indicator` on a spinner labeled "Đang lưu đơn vị…". The spinner is visible only while the request runs (`htmx-indicator` / `htmx-request`).
    - A successful add still selects the new unit. An empty name still shows "Nhập tên đơn vị phối hợp."
  - **Verify (localhost):** as `cb.htkn`, on an activity form, add a partner unit and confirm the spinner appears and the new name is selected. Submit an empty name and confirm the Vietnamese error.
  - **Estimate:** S

- [x] **IMP-13 — Bind labels, keyboard order, and focus on the entry screens**
  - **Priority:** P2
  - **Why:** object-split labels are not tied to their inputs, field-split controls have no label, and the partner-unit text input's label is not tied to `id_ten_don_vi_moi`. A keyboard user cannot tell which control is active if focus is restyled away.
  - **Evidence:** `templates/entry/phan_loai_grid.html` (object `<label>` without `for`; field `<select>` and value `<input>` without a label); `templates/activities/hoat_dong_form.html` partner block. Review §3 row "Responsive/accessibility", §5.5. Login, activity fields, and indicator totals already use `form-label` with `for`.
  - **Files:** `templates/entry/phan_loai_grid.html`, `templates/activities/hoat_dong_form.html`, `templates/entry/_indicator_form.html`
  - **Depends on:** IMP-11
  - **Acceptance criteria:**
    - Every input on the activity form, the monthly phiếu, the project phiếu, and the field grid has a visible label or an `aria-label`, including the search field from IMP-11 and the value next to it.
    - Tab order on those screens reaches every control and the save button. Focus uses the browser or Tabler ring; do not remove outlines.
    - While walking those screens, darken any text that is light gray on white. Do not restyle the rest of the app.
  - **Verify (localhost):** with the mouse unplugged, sign in, open an activity, tab through partner units and the field grid, save, and confirm focus was always visible. Repeat on a monthly phiếu and a project phiếu.
  - **Estimate:** M

- [x] **IMP-14 — Add the missing entry hints**
  - **Priority:** P2
  - **Why:** several empty sentences already exist ("Chưa có chỉ tiêu nào được cấu hình cho biểu mẫu này.", "Chưa có dòng hỗ trợ nào."). The three entry forms still do not say what draft save does, or that the monthly comparison figures are read-only.
  - **Evidence:** `templates/entry/phieu_form.html`, `templates/entry/phieu_thang.html`, `templates/entry/phieu_du_an.html`, `templates/entry/_indicator_form.html`. Review §5.5.
  - **Files:** `templates/entry/phieu_form.html`, `templates/entry/phieu_thang.html`, `templates/entry/phieu_du_an.html`, `templates/entry/_indicator_form.html`
  - **Depends on:** —
  - **Acceptance criteria:**
    - Activity and monthly forms show "Lưu nháp giữ số chưa đủ. Gửi duyệt yêu cầu các chỉ tiêu bắt buộc."
    - The monthly form shows "Tháng trước và lũy kế năm lấy từ số đã duyệt, không nhập trên phiếu này."
    - The project form shows "Mỗi dòng là một lần hỗ trợ. Số chuyên gia không được âm."
    - The field-tree sentence stays the one from IMP-09. The 1–5 message stays the one from IMP-04.
  - **Verify (localhost):** as `cb.htkn`, open an activity phiếu, a monthly phiếu, and a project phiếu, and read the three sentences. Save a draft with a required indicator empty and confirm it still saves. Gửi duyệt and confirm the existing required message.
  - **Estimate:** S

---

## P3 — Polish

- [ ] **IMP-15 — Batch the per-activity report queries**
  - **Priority:** P3
  - **Why:** gap detection and the HTKN activity list each ask whether a phiếu exists, once per activity. Indicator ids for a gap are queried once per activity that has no phiếu.
  - **Evidence:** `apps/reporting/report_data.py` `_activity_gaps`, `_activity_indicator_ids`, `activities_for_department`. `rollup_by_department` is one rollup per phòng (three departments) and can stay. Review §5.4.
  - **Files:** `apps/reporting/report_data.py`
  - **Depends on:** IMP-06
  - **Acceptance criteria:**
    - One query loads the phiếu flags for the activities in the period. One query loads the indicator ids used by those gaps. The preview text stays the same, including the ad-hoc `noi_dung` and `ket_qua` added by IMP-06.
    - Do not rewrite `rollup`.
  - **Verify (localhost):** leave one organized HTKN activity without a phiếu. Open the quarter preview and confirm the sentence "Hoạt động “…” đã tổ chức nhưng chưa có phiếu kết quả." In `manage.py shell` with `DEBUG` query logging, call `activities_for_department` for a period that contains several activities and confirm the query count stays flat when another activity is added.
  - **Estimate:** M

- [ ] **IMP-16 — Stop an export that would build an unbounded file in memory**
  - **Priority:** P3
  - **Why:** `.xlsx` and `.docx` are built entirely in a `BytesIO`, then held again as the saved file. A localhost kỳ with a very large activity list will grow without a warning.
  - **Evidence:** `apps/reporting/xlsx_export.py` and `apps/reporting/docx_export.py` (both return `BytesIO.getvalue()`); `apps/reporting/exports.py` `content_stream`. Review §5.4.
  - **Files:** `apps/reporting/xlsx_export.py`, `apps/reporting/docx_export.py`, `apps/reporting/views.py`
  - **Depends on:** IMP-05, IMP-06
  - **Acceptance criteria:**
    - Before building, if indicator rows plus breakdown rows plus activity and project rows exceed 10,000, do not build the file. The preview shows "Báo cáo quá lớn để xuất trên máy này (trên 10000 dòng). Thu hẹp kỳ hoặc phòng rồi xuất lại."
    - The constants live next to the exporters. A normal three-department month, which is far under 10,000 data rows, still exports. The IMP-05 precision gate still runs for files that are built.
  - **Verify (localhost):** export the current HTKN month and confirm a file downloads. In `manage.py shell`, call the size check with a fake row count of 10,001 and confirm the Vietnamese sentence and no bytes. `ruff check .` exits 0.
  - **Estimate:** S

- [ ] **IMP-17 — Cap Excel uploads and reject oversized zip contents**
  - **Priority:** P3
  - **Why:** the upload checks the `.xlsx` suffix and then lets openpyxl read the zip. A large or highly compressed file will spend disk and memory on the dev machine. The preview still must not write `SoLieu`.
  - **Evidence:** `apps/reporting/forms.py` `XlsxUploadForm.clean_file`; `apps/reporting/xlsx_import.py` `parse_workbook`; `apps/reporting/views.py` `nhap_xlsx`. No `DATA_UPLOAD_MAX_MEMORY_SIZE` override in `config/settings.py`. Review §3 row "Upload Excel".
  - **Files:** `apps/reporting/forms.py`, `apps/reporting/xlsx_import.py`
  - **Depends on:** —
  - **Acceptance criteria:**
    - Reject a file larger than 5 MiB with "Tệp vượt quá dung lượng cho phép (5 MB)."
    - Before `load_workbook`, read the zip central directory. Reject more than 64 entries, or a declared uncompressed total over 32 MiB, with "Tệp Excel có quá nhiều thành phần hoặc nội dung giải nén vượt quá giới hạn." Do this from the headers, before inflating the entries.
    - A normal export still previews. A wrong header still shows "Tệp Excel không đúng mẫu báo cáo." The preview still writes nothing.
  - **Verify (localhost):** upload this app's HTKN export and confirm the preview. Upload a file over 5 MiB and confirm the size sentence. In `manage.py shell`, build a zip whose central directory claims an uncompressed size over 32 MiB and confirm the guard raises before openpyxl reads cells. `ruff check .` exits 0.
  - **Estimate:** M

- [ ] **IMP-18 — Make the Axes lockout threshold a setting, and keep today's value**
  - **Priority:** P3
  - **Why:** lockout runs at 10 failures. `TASKS.md` M1-T05's verify text says the Vietnamese message appears after five. Those two were never reconciled. The number itself waits on a decision; the code should show which value is live.
  - **Evidence:** `config/settings.py` `AXES_FAILURE_LIMIT = 10`, cooloff 15 minutes, message "Tài khoản tạm khóa vì đăng nhập sai quá nhiều lần. Vui lòng thử lại sau."; `TASKS.md` M1-T05. Review §4 item 9.
  - **Files:** `config/settings.py`, `.env.example`
  - **Depends on:** —
  - **Acceptance criteria:**
    - `AXES_FAILURE_LIMIT` reads `AXES_FAILURE_LIMIT` from the environment and defaults to 10 when the variable is absent. Cooloff stays 15 minutes. The Vietnamese lockout sentence stays.
    - `.env.example` documents the variable and states that M1-T05's verify text says five, and that the running default remains 10 until the product owner decides.
    - Do not change the seeded passwords or turn on proxy handling.
  - **Verify (localhost):** with the variable unset, `manage.py shell` prints `10` for `settings.AXES_FAILURE_LIMIT`. Set it to `3` in the environment for one process, fail login three times as `cb.htkn`, and confirm the cooloff sentence. Put the variable back. A successful login still reaches `/`.
  - **Estimate:** S

---

## Blocked on decision

No task above invents these. Suggested default is what the code does today, or what IMP-05 already chooses for the file format.

| Item | Why it is blocked | Who decides | Suggested default |
|---|---|---|---|
| Official QĐ 36 / TT 24 list and who signs a change (Q1) | IMP-09 only loads a file. The repo has a 3-row sample and zero database rows. Inventing codes would mis-classify real phiếu. | Owner of the field list | Keep the empty state until a signed CSV replaces `fixtures/linh_vuc.csv`. |
| Late flag threshold (Q2) | `rollup.py` marks chậm when percent of plan is below the linear year elapsed in `Asia/Ho_Chi_Minh`. Another rule changes official reports. | Product owner | Keep the linear year fraction. |
| Who may edit an approved phiếu or a closed period | Reopen is already department head plus a comment. A second editor, or edits after `khoa` without reopen, is a different rule. IMP-01 and IMP-03 enforce the current rule. | Product owner | Keep reopen-with-comment. Closed months stay read-only. |
| Legacy HTKN and GDCN workbooks (Q7) | No cell map. The importer only previews this app's own export. | Data owner | Do not import. Keep `inspect_legacy_workbook`. |
| Axes limit, 5 or 10 | M1-T05 verify says five. The setting is 10. IMP-18 exposes the setting and leaves 10. | Product owner | Keep 10 until they write the number down. |
| All 18 digits of `SoLieu` inside Excel | A numeric `.xlsx` cell cannot store `Decimal(18, 4)` exactly. Text cells would break M7-T04. | Product owner | IMP-05 rejects the export and names the stored value. |
| Official Word letterhead (Q6) | No letterhead file was supplied. | Whoever owns the center template | Keep the plain templates in `report_templates/`. |
| Q4, Q5, Q8, Q10, Q11, Q12, Q13 | Shipped defaults: R&D as monthly `latest`; only months are lockable periods; optional "Đánh giá hiệu quả"; bulk approve blocked on `clean()` or a missing required indicator; notices are the home page and the gap list; center head sits in `BGĐ`; one role per user. | Product owner | Keep the `TASKS.md` §4.6 defaults. |

## Deferred

Excluded on purpose. One line each.

- Production settings (`DEBUG`, placeholder `SECRET_KEY`, HSTS, HTTPS redirect, secure cookies) — review §3 and §5.1; this phase stays on localhost with `DEBUG` on.
- Public `/media/` downloads while `DEBUG` is on — review §3; private storage is a deployment change.
- gunicorn, proxy, Docker, `collectstatic`, staging, migrate/rollback — review §5.2; no network deploy in this phase.
- Backup, restore, retention copies of database and media — review §5.2.
- Application logging, health endpoint, uptime, disk alerts, maintenance mode — review §5.2.
- Custom 404/500 pages — review §3 marks them Low, and Django does not use `handler404` / `handler500` while `DEBUG` is true. Turning `DEBUG` off is the deferred settings item, so the pages cannot be accepted on this localhost setup.
- pytest, empty `accounts/tests.py` and `catalog/tests.py`, race tests, upload tests, CI — review §5.3. Manual checks above replace them for this phase.
- CVE scan and SBOM — review §3; transitive CVEs were already marked unverified.
- Catalog line-by-line sign-off of the 96 seeded indicators — review §3; a data-owner meeting, not a code change.
- Password reset, MFA, and session-age policy — review §5.1; the manual already tells the officer to contact admin. Not required to enter data on localhost.
- Revoking the seeded `admin` superuser and the fixed dev passwords — review §3; M1-T07 requires those accounts. IMP-01 locks business models instead.
- Axes behind a reverse proxy — review §4 item 9; there is no proxy in this phase.
- PII, retention, access-log policy, runbooks, role manuals, training, support SLA — review §5.5 and §5.6.
- Volume forecast and load tests — review §8; the list and query tasks above are the localhost slice.

## Traceability

| Review item | Where it went | `TASKS.md` |
|---|---|---|
| §4.1 QĐ 36 / TT 24 tree | IMP-09; official file blocked (Q1) | M2-T03, M2-T12 |
| §4.2 satisfaction 1–5 | IMP-04 | M2-T10, Q3 |
| §4.3 Excel precision | IMP-05; 18-digit fidelity blocked | M7-T04 |
| §4.4 report sections | IMP-06; indicator stacking already present | M7-T03, M7-T04, M7-T06 |
| §4.5 month screen | IMP-07 | M4-T09 |
| §4.6 copy previous plan | IMP-08 | M2-T07 |
| §4.7 admin bypass | IMP-01; seeded superuser stays | M1-T07, M5 |
| §4.8 duplicate primary / lock race | IMP-02, IMP-03 | M4-T01, M4-T09, M5-T02 |
| §4.9 Axes 10 vs 5 | IMP-18; the number is blocked | M1-T05 |
| §3 catalog sign-off | Deferred | M2-T09, M2-T10 |
| §3 production settings, media, deploy | Deferred | — |
| §3 backup, logs, health | Deferred | — |
| §3 upload | IMP-17 | M7-T08 |
| §3 localhost credentials | Deferred; business writes covered by IMP-01 | M1-T07 |
| §3 tests and CI | Deferred | M10-T02 |
| §3 lists, N+1, field tree in the form | IMP-10, IMP-15, IMP-11 | M3-T02, M3-T05, M4-T08, M7 |
| §3 password, MFA, session | Deferred; Axes covered by IMP-18 | M1-T05 |
| §3 legacy workbooks | Blocked (Q7) | M7-T09 |
| §3 manuals, retention, PII | Deferred | — |
| §3 accessibility | IMP-13 | M10 |
| §3 CVE | Deferred | — |
| §3 custom 404/500 | Deferred | — |
| §5.5 loading indicator, empty states | IMP-12, IMP-14 | — |
| Q2 late flag | Blocked | M6-T06 |
| Q4, Q5, Q6, Q8, Q10, Q11, Q12, Q13 | Blocked | owning tasks in §4.6 |
| Q9 badge labels | No change; review §6 already accepts the shipped labels | M4-T04 |

## Suggested execution order

Do the tasks in id order. IMP-03 waits on IMP-02, IMP-06 waits on IMP-05, IMP-11 waits on IMP-09, IMP-13 waits on IMP-11, and IMP-15 / IMP-16 wait on IMP-06. The others can start as soon as the earlier id in the same files is done.

The first three to implement:

1. **IMP-01 — Stop business writes through `/admin/`**
2. **IMP-02 — One primary phiếu per target**
3. **IMP-03 — Re-check the period and the phiếu inside the write**

Then IMP-04, IMP-05, IMP-06, IMP-07, IMP-08, IMP-09, IMP-10, IMP-11, IMP-12, IMP-13, IMP-14, IMP-15, IMP-16, IMP-17, IMP-18.

## Effort summary

| Priority | Tasks | S | M | L |
|---|---:|---:|---:|---:|
| P0 | 5 | 3 | 2 | 0 |
| P1 | 4 | 0 | 3 | 1 |
| P2 | 5 | 3 | 2 | 0 |
| P3 | 4 | 2 | 2 | 0 |
| **Total** | **18** | **8** | **9** | **1** |

Blocked items: 8 rows. Deferred items: 14 lines. No application code was modified while writing this file.
