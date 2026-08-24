# task.md — MyMoney To-Do List

> Phased execution checklist. Update status as you work. The current phase is **Phase 3**.
> When Phase 3 is fully done, move its items under `## Done` and unmute Phase 4.

Legend: `[ ]` pending · `[x]` done · `[~]` in progress

---

## Phase 3 — Report Dasar (current)

### A. Report service (US-11, US-16, US-17)
- [x] Create `backend/app/core/report_service.py` — **SQL-only** aggregation
      (`SUM`/`GROUP BY`, DATABASE.md §3.4, never Python loops).
- [x] `parse_period_arg(arg, tz)` — hari-ini/today, minggu-ini/week/this-week,
      bulan-lalu/last-month/previous-month, default = bulan-ini; boundaries in the
      user's timezone; kebab/space normalization.
- [x] `period_label(arg)` — human-readable label for the reply.
- [x] `get_report_summary(db, user_id, *, start_date, end_date)` — totals per type
      + per-category breakdown (ordered by `SUM DESC`), `net = income - expense`.
- [x] Create `backend/app/schemas/report.py` — `CategoryTotal` +
      `ReportSummaryResponse`.

### B. REST API (US-16)
- [x] Create `backend/app/api/reports.py` — `GET /api/reports/summary?period=month`
      (or `?start=&end=` custom range; 422 invalid period / inverted range).
- [x] Register router in `main.py`.
- [x] No migration needed (read-only).

### C. Telegram `/report` (US-17)
- [x] Add `/report [period]` handler in `core/telegram_service.py` (section 3.6):
      user timezone via `db.get(User, user_id)`, DB-only summary (no LLM),
      `_format_report()` renders income/expense/net + per-category lines.

### D. Tests
- [x] `tests/test_report_service.py` — unit: `parse_period_arg` boundaries for
      every keyword + default + normalization; integration (real DB): seeded
      transactions with fixed dates → totals & breakdown match hand-computed
      values; out-of-period excluded; empty period → zeros.
- [x] `tests/test_reports_api.py` — TestClient: 401, default month, valid periods,
      invalid period 422, custom range, inverted range 422.
- [x] `tests/test_telegram_service.py` — `/report` requires link, default period,
      `minggu ini` → "this week", user timezone resolution.

### E. Verification
- [x] `ruff check app/ tests/ --no-cache && black --check app/ tests/` clean.
- [x] `pytest tests/ -q` — **88 passed** (66 Phase 2 + 22 new Phase 3).
- [x] Manual E2E live: register → account (201) → income + expense this month +
      expense last month → `/api/reports/summary` totals & categories correct;
      `?period=last-month` shows only the old expense; `?period=bogus` → 422;
      Telegram `process_telegram_update(/report)` returns formatted summary;
      `/report bulan lalu` → zeros.
- [x] Bug fixed during E2E: `api/accounts.py` used `func.case(..., else_=-1)`
      which SQLAlchemy 2.0 rejects (`Function.__init__() got an unexpected
      keyword argument 'else_'`) → switched to `case(...)` imported from
      `sqlalchemy`; account create now 201 and balance computation works.
- [x] Data check: report endpoints are read-only (no writes, no migration).

### Phase 3 sign-off
- [x] Confirm aggregation is SQL-only (no Python-side summing).
- [x] Confirm `/report bulan-ini` works in Telegram (ROADMAP Fase 3 checkpoint).
- [x] Confirm REST endpoint returns the same data for Android (US-16).
- [x] Confirm tests + lint + E2E green → update `IMPLEMENTATION_PLAN.md`,
      `walkthrough.md`, and this file. (Phase 3 complete, ready for Phase 4.)

---

## Phase 4 — Android App (not started)
- [ ] Kotlin + Compose project, MVVM, auth, transactions list, report charts.

## Phase 5 — OCR Foto Nota (not started)
- [ ] `receipt_service` + vision model via `call_llm()`, multi-item schema,
      confidence handling, image storage.

## Phase 6 — Deploy Produksi & Hardening (not started)
- [ ] VPS provisioning, Nginx + Let's Encrypt, resource limits, deploy CI, monitoring.

---

## Done
- [x] **Phase 2 — Telegram Integration + Text Parsing** ✅
      (LLM gateway via DeepSeek `call_llm()`, locked categories → "Other",
      audit trail, service-layer API, slowapi rate limiting,
      pending-confirmation flow US-05/US-08 — 66 tests passed, E2E verified live).
- [x] **Phase 0 — Setup Fondasi** (docker-compose, Dockerfile, Alembic `0001`,
      seed categories, `.env.example`, pre-commit, CI lint scaffold).
- [x] **Phase 1 — Backend Inti + Autentikasi** (auth/JWT/Argon2, transactions CRUD +
      cursor pagination, accounts computed balance, categories).
  - ⚠️ Note: REST endpoints still carry business logic/direct ORM; partly addressed
      by Phase-2 item D.
