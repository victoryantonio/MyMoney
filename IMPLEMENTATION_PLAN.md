# IMPLEMENTATION_PLAN.md — MyMoney

> Planning doc for the **current** phase of work.
> Each phase gets its own section. When work moves to a new phase, this file is
> edited so the "Current Phase" points at the active one and completed phases
> move under `## Completed Phases`.

**Current Phase: Phase 3 — Report Dasar**

---

## Phase 3 — Report Dasar

### 1. Goal Description

**Primary goal:** Give the user a summary of income/expense per period (daily,
weekly, monthly) with a per-category breakdown — available both from Telegram
(`/report` command, US-17) and from the REST API (for the Android charts,
US-16).

**Current reality (verified in code, repo after Phase 2):**
Phase 2 shipped the full Telegram flow (linking, NL parsing → pending →
`/confirm`, `/undo`, `/edit`, audit trail, rate limiting) on top of the Phase 1
REST core (transactions, accounts, categories). All data lives in PostgreSQL and
all mutation logic lives in `core/` services. Nothing aggregates by period yet —
reporting is the natural next read-only layer.

**Definition of done (ROADMAP §Fase 3 checkpoint):**
- `/report bulan-ini` in Telegram shows a short income/expense summary per
  category (text, no charts in v1).
- `GET /api/reports/summary` returns the same data as JSON for the Android app.
- All aggregation happens in **SQL** (`SUM`/`GROUP BY`), never in Python loops
  (DATABASE.md §3.4).
- Periods supported: today, this week, this month (default), last month —
  keywords accepted in Indonesian and English.
- No migration needed (read-only queries).

**Out of scope for this phase:** charts/graphs rendering (Android side, Phase 4),
receipt/vision OCR (Phase 5), aggregation caching (ROADMAP: none in v1).

### 2. User Review Required

- [x] **Report period format for Telegram.** ROADMAP checkpoint uses `/report
      bulan-ini`. **Resolved:** the `/report` command takes an **optional** period
      arg (`/report` → this month; `/report hari-ini`, `/report minggu ini`,
      `/report bulan lalu`) and parses Indonesian + English keywords via
      `core/report_service.py::parse_period_arg`.
- [x] **Timezone for "today"/"this month".** Period boundaries are computed in the
      user's own timezone (`user.timezone`, default `Asia/Jakarta`), so "today"
      means *their* today, not the server's.

### 3. Open Questions

1. ~~Report period format for Telegram `/report` parsing.~~ **Resolved:** optional
   arg, kebab/space-normalized, Indonesian + English keywords (see §2).
2. ~~Whether to cache aggregates.~~ **Resolved for v1:** no caching — reports are
   read-only `SUM`/`GROUP BY` queries that run in milliseconds on a personal
   dataset; revisit if the Android dashboard polls frequently (Phase 4).
3. **Category ordering in the report:** decided — descending by total amount
   (biggest first), enforced in SQL via `ORDER BY SUM(total_amount) DESC`.
4. **Limit on the number of categories shown in Telegram:** a text message should
   stay short — v1 shows all rows, but caps are trivial to add later if a user
   has many categories.

### 4. Proposed Changes

#### 4.1 `core/report_service.py` (new)
- `parse_period_arg(arg, tz) -> (start, end)` — resolves period keywords to an
  inclusive `[start, end)` boundary pair in the user's timezone:
  - `hari-ini`/`today` → today 00:00 → +1 day
  - `minggu-ini`/`week`/`this-week` → Monday 00:00 → +7 days
  - `bulan-lalu`/`last-month`/`previous-month` → first of previous month → first
    of this month
  - default/empty/`bulan-ini` → first of this month → first of next month
- `period_label(arg)` — human-readable English label for the reply text.
- `get_report_summary(db, user_id, *, start_date, end_date)` — **SQL-only**
  aggregation (DATABASE.md §3.4):
  - totals: `SELECT type, SUM(total_amount) FROM transactions WHERE user_id=? AND
    transaction_date >= ? AND transaction_date < ? GROUP BY type`
  - breakdown: same filter joined to `categories`, grouped by
    `(category.name, type)`, ordered by `SUM(total_amount) DESC`
  - `net = income - expense`

#### 4.2 `schemas/report.py` (new)
- `CategoryTotal` — `name`, `type`, `total` (Decimal).
- `ReportSummaryResponse` — `start_date`, `end_date` (exclusive), `total_income`,
  `total_expense`, `net`, `categories: list[CategoryTotal]`.

#### 4.3 `api/reports.py` (new, US-16)
- `GET /api/reports/summary?period=month` (default) — or explicit
  `?start=&end=` for custom ranges; 422 for invalid period / inverted range.
- Auth: `require_active_user`; timezone from `current_user.timezone`.
- Registered in `main.py` (`app.include_router(reports.router)`).

#### 4.4 `core/telegram_service.py` — `/report` handler (US-17)
- New section 3.6 before the NL branch: `/report [period]` → resolve the user's
  timezone (`db.get(User, user_id)`), call `parse_period_arg` + `get_report_summary`,
  render via `_format_report()` (income/expense/net + per-category lines).
- Uses only DB aggregation — **no LLM call** for reports.

### 5. Verification Plan

1. `ruff check app/ tests/ --no-cache && black --check app/ tests/` — clean.
2. `pytest tests/ -q` — full suite passes (88 tests after Phase 3; additions):
   - `tests/test_report_service.py` — unit: `parse_period_arg` boundaries for
     every keyword + default, normalization ("bulan ini" == "bulan-ini"),
     `period_label`; integration (real DB): seeded transactions with fixed dates
     → totals & per-category breakdown match hand-computed values; out-of-period
     rows excluded; empty period → zeros.
   - `tests/test_reports_api.py` — TestClient: 401 without token, default month,
     all valid periods 200, invalid period 422, custom range 200, inverted range
     422.
   - `tests/test_telegram_service.py` — `/report` requires link; default period;
     `minggu ini` → "this week"; user timezone resolution.
3. **Manual E2E (live):** register → create account → create income + expense
   (this month) + one expense last month → `GET /api/reports/summary` shows
   month totals & per-category rows; `?period=last-month` shows only the old
   expense; Telegram `process_telegram_update(/report)` returns the formatted
   text summary; `/report bulan lalu` returns zeros.
4. **Negative cases:** invalid period → 422; start ≥ end → 422; unlinked Telegram
   user → "not linked yet".
5. **Data check:** no writes — report endpoints are read-only (no migration, no
   new rows).

---

## Completed Phases

### Phase 2 — Telegram Integration + Text Parsing ✅

### 1. Goal Description

**Primary goal:** Ship a working Telegram end-to-end flow where a linked user can
send a natural-language message (e.g. `beli kangkung 5k`) and have a validated
transaction persisted and confirmed back in chat.

**Current reality (verified in code, repo at `5e67762 "Phase 1"`):**
Much of Phase 2 exists and runs — webhook endpoint, `/start` account linking,
`/undo`, `/edit`, and a DeepSeek text parser (`core/nlu_parser.py` via the
`core/llm_client.py::call_llm()` gateway). The
channel works. **However, it violates several explicit architecture rules** in
`CODING_RULES.md §2.4 / §2.7 / §2.9.B` that are marked "Tidak Boleh Dilanggar."
Phase 2 is therefore not "done, just polish" — it needs architectural
refactoring to be _correct_ before Phase 3 builds on top of it.

**Definition of done (CODING_RULES-compliant):**
- All LLM calls go through a single `core/llm_client.py::call_llm()` gateway (no
  direct DeepSeek/LLM-provider HTTP calls from any service/parser).
- LLM output is validated against a **locked category list** (no auto-creating
  arbitrary categories from free-form LLM category strings).
- Audit trail is actually written for every create/edit/delete transaction and
  login (currently `AuditLog` model exists but is never used).
- API layer no longer contains business logic / direct ORM queries for the
  Telegram paths (single source of truth per `ARCHITECTURE.md §1`).
- Rate limiting is enabled on public endpoints (`slowapi` is already a dependency).
- LLM parse results are gated by a **pending-confirmation state**: they land in
  `pending_transactions` and only commit on explicit `/confirm` (REQUIREMENTS
  US-05/US-08, CODING_RULES §2.4) — never a direct save from a parse.

**Out of scope for this phase:** receipt/vision OCR (Phase 5), report service
(Phase 3), Android app (Phase 4).

### 2. User Review Required (if any)

- [x] **Confirm Direct Save vs. pending-confirmation.** ROADMAP §Fase 2 chose
      *Direct Save* (LLM parse → immediate commit), which contradicts REQUIREMENTS
      US-05 and CODING_RULES §2.4. **Resolved: pending-confirmation wins** — NL text
      and `/edit` results create a `PendingTransaction` (10-min expiry) and commit
      only on `/confirm`; `/cancel` discards. New commands `/confirm` + `/cancel`
      added; pending row is deleted in the same DB commit as the resulting
      transaction (no crash window).
- [x] Confirm that the Telegram flow should **create a new custom category** when the
      LLM returns a name not in the DB, vs. rejecting/substituting with "Other."
      **Resolved: locked-list wins** — LLM categories never auto-create; unknown
      names resolve to the seeded global "Other" of the matching type
      (`get_or_create_category(..., allow_create=False)`). Custom categories remain
      available on the explicit REST path only.

### 3. Open Questions

1. **Direct Save or pending confirmation?** ~~(see §2 — blocking decision)~~
   **Resolved: pending-confirmation.** Implemented as `core/pending_service.py`
   + `pending_transactions` table (migrations `0002`, `0003`), `/confirm` +
   `/cancel` Telegram commands, and a `pending` parameter on
   `transaction_service.create/update_transaction_internal` that removes the
   pending row in the same commit.
2. **Which LLM models to keep in the fallback chain?** ~~Current chain is
   `z-ai/glm-5.2:free` → `meta-llama/llama-3.3-70b-instruct:free` →
   `openrouter/free`.~~ **Resolved — provider switched to DeepSeek.** Text uses
   `deepseek-v4-flash` (fallback `deepseek-v4-pro`), vision uses
   `deepseek-v4-flash-vision-exp` (defined in `core/llm_client.py`). Base URL
   `https://api.deepseek.com/v1` (call path `/v1/chat/completions`). **IDs
   verified live against the API** — the API rejects the VS Code *display
   labels* (`DeepSeek-V4-Flash-0731` etc.) and only accepts the lowercase names.
3. **Category-matching granularity:** match LLM category against DB by exact
   name, fuzzy/contains, or only exact + fallback "Other"? Affects
   `get_or_create_category`.
4. **Rate-limit thresholds** for `/api/telegram/webhook` and REST — what's
   appropriate for a personal single-user bot? (Default plan: e.g. 20/min LLM,
   higher for authenticated REST.)
5. **Audit persistence for the `/undo`/`/edit` flows** — should these also write
   `AuditLog` rows (they're transaction mutations)? (I believe yes — confirm.)
6. **`.env.example` `DATABASE_URL`** uses `postgresql+psycopg`; confirm the driver
   string is correct relative to `requirements.txt` (`psycopg[binary]`).

### 4. Proposed Changes

#### 4.1 Single LLM gateway — `core/llm_client.py` (new)
- Extract model constants into module-level constants:
  - `TEXT_MODELS = ["deepseek-v4-flash", "deepseek-v4-pro"]`
  - `VISION_MODELS = ["deepseek-v4-flash-vision-exp"]` (Phase 5 use).
- Implement
  `async def call_llm(messages, *, models, temperature=0.0, parser=None) -> T | None`
  that owns: HTTP client, `Authorization: Bearer <DEEPSEEK_API_KEY>` header,
  per-model try-loop, markdown-fence cleanup (`_extract_content`), and explicit
  error handling (timeout, rate limit, invalid response) with structured logging.
  Returns the parsed value on success (via the `parser` callback) or `None` when
  all models fail. URL is `{deepseek_base_url}/chat/completions`; timeout 30.0s.
- Refactor `core/nlu_parser.py` to call `call_llm()` instead of `httpx` directly —
  remove its local `models_to_try`, headers, and try-loop. The parser callback
  (`_parse_llm_json`) does the JSON→Pydantic validation.

#### 4.2 Locked-category validation
- In `core/transaction_service.py`, change `get_or_create_category` behavior for
  **LLM-originated** categories: look up the category by name against the global +
  user set; if not found, do **not** auto-create — return the user's/global
  "Other" category (or signal the caller to reject). Keep auto-create only for
  explicit REST category creation (user intent).
- Pydantic validation in `nlu_parser` should also constrain the category field
  against a supplied allowed set where possible (CODING_RULES §2.4).

#### 4.3 Wire up audit trail — `core/audit_service.py` (new)
- Add `record_audit(db, *, user_id, action, entity_type, entity_id, old_value,
  new_value, source, ip_address=None)` service helper that inserts an `AuditLog`.
- Call it from `core/transaction_service` (create/update/delete) and the login
  flow (`api/auth.py` success/failure). Ensure `/undo` and `/edit` (which mutate
  transactions in `core/telegram_service.py`) also record audit entries.

#### 4.4 Move business logic out of the API layer (Telegram + transactions paths)
- `api/telegram_webhook.py`, `api/telegram_linking.py`, `api/auth.py`: keep thin.
- Refactor `core/telegram_service.py` to own the full transaction mutation logic
  (it already uses service-layer helpers — verify no direct ORM remains).
- Ensure `core/transaction_service.py` exposes the complete crate/update/delete
  surface used by the REST routes, so REST can call it too (Phase 4 reuse).

#### 4.5 Rate limiting — configure `slowapi`
- Add `SlowAPIMiddleware` (or per-route `@limiter.limit`) in `main.py`/`deps.py`.
- Set a sensible default limit for webhook (LLM-bound) vs. authenticated REST.

#### 4.6 Minor/clarifying
- Prompt-injection defenses (hardcoded system prompt, escaped user input,
  JSON-schema instruction) live in the **domain parser** (`core/nlu_parser.py`,
  `_SYSTEM_PROMPT`) per CODING_RULES §2.9.B. `llm_client.py` stays transport-only:
  it owns auth, HTTP, fallback, and fence-cleanup — not prompt text. This keeps a
  single gateway for all providers while letting each domain define its own prompt.

### 5. Verification Plan

1. `ruff check . && black --check .` — clean (no new violations).
2. `pytest tests/ -v` — existing suite passes incl. `test_nlu_parser.py` (mocked,
   no real LLM call). Add tests (✅ all present, 50 pass):
   - `llm_client` fallback chain (first model fails → second succeeds; all fail → None;
     missing API key → None without calling the provider) — `tests/test_llm_client.py`.
   - category not found → resolves to "Other", does **not** create new category —
     `tests/test_category_locked.py`.
   - audit log written on transaction create/update/delete and login —
     `tests/test_audit_service.py`.
3. **Manual E2E (locally via docker-compose):**
   - `docker-compose up -d --build` → `/health` = `{"status":"ok"}`.
   - `docker-compose exec backend alembic upgrade head`.
   - Register → login → get JWT.
   - Simulate webhook: `POST /api/telegram/webhook` with
     `X-Telegram-Bot-Api-Secret-Token` and a valid update payload; confirm a
     transaction row is created and a reply is drafted.
   - `/start` → get link URL → complete linking → send `beli kangkung 5k`.
4. **Negative cases:**
   - Invalid webhook secret → 403.
   - Unlinked user sends text → "not linked" reply, no DB write.
   - LLM returns invalid JSON / all models fail → graceful error message, no crash.
5. **Data check:** no new category rows created for arbitrary LLM categories
   (query `categories` before/after).

---

## Phase 0 — Setup Fondasi ✅
(docker-compose, Dockerfile, Alembic `0001`, seeds, lint config, CI scaffolding)

## Phase 1 — Backend Inti + Autentikasi ✅
(auth, JWT, Argon2, transactions CRUD + cursor pagination, accounts with computed
balance, categories)
- ⚠️ Note: REST endpoints originally contained business logic / direct ORM; the
  Phase-2 refactor (§4.4) moved mutation logic into `core/` services.
