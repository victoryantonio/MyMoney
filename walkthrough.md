# walkthrough.md — MyMoney Phase 3 Execution Guide

> This is the concrete, step-by-step "how to actually do Phase 3" companion to
> `task.md`. Every step names the real file to touch and what to change. Run
> verification tasks at each checkpoint. **Work is grounded in the repo state at
> the end of Phase 2 (all 66 tests green).**

Phase 3 = **Report Dasar** — read-only income/expense summaries per period
(today / this week / this month / last month) with a per-category breakdown,
served both to Telegram (`/report`, US-17) and the REST API (US-16 for Android).

---

## Step 0 — Decision gate (before writing code)

Read `IMPLEMENTATION_PLAN.md §2/§3`. Resolved decisions:

1. **Aggregation location.** DATABASE.md §3.4 mandates **SQL** `SUM`/`GROUP BY`,
   never Python loops. All report math lives in `core/report_service.py` queries.
2. **Period format.** `/report` takes an optional arg; keywords accepted in
   Indonesian + English (`hari-ini`/`today`, `minggu ini`/`this week`,
   `bulan lalu`/`last month`, default `bulan ini`). Boundaries computed in the
   **user's timezone** (`user.timezone`, default `Asia/Jakarta`).
3. **Caching.** None in v1 (ROADMAP) — queries are cheap on a personal dataset.

---

## Step 1 — Report service (`core/report_service.py`) + schema

### 1.1 Create `backend/app/schemas/report.py`

```python
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel


class CategoryTotal(BaseModel):
    name: str
    type: str  # "income" | "expense"
    total: Decimal


class ReportSummaryResponse(BaseModel):
    start_date: datetime
    end_date: datetime      # exclusive
    total_income: Decimal
    total_expense: Decimal
    net: Decimal
    categories: list[CategoryTotal]
```

### 1.2 Create `backend/app/core/report_service.py`

Three pieces, all pure/DB-only:

- `_normalize(arg)` — collapse whitespace + lowercase into kebab keywords
  (`"bulan ini"` → `"bulan-ini"`).
- `parse_period_arg(arg, tz) -> (start, end)` — inclusive `[start, end)` pair in
  the user's timezone:
  - `hari-ini`/`today` → `[today 00:00, +1 day)`
  - `minggu-ini`/`week`/`this-week` → `[Monday 00:00, +7 days)`
  - `bulan-lalu`/`last-month`/`previous-month` → `[1st prev month, 1st this month)`
  - default/empty/`bulan-ini` → `[1st this month, 1st next month)`
- `period_label(arg) -> str` — `"today"` / `"this week"` / `"last month"` /
  `"this month"`.
- `get_report_summary(db, user_id, *, start_date, end_date)` — **SQL-only**
  (DATABASE.md §3.4):
  - totals: `select(Transaction.type, func.sum(Transaction.total_amount))
    .where(user_id == ?, transaction_date >= start, < end).group_by(type)`
  - breakdown: same filter `join(Category, category_id)`, group by
    `(Category.name, Transaction.type)`, `order_by(func.sum(...).desc())`
  - `net = income - expense`

> Aggregation must never loop in Python — one `GROUP BY` query per concern.

---

## Step 2 — REST endpoint (`api/reports.py`, US-16)

Create `backend/app/api/reports.py`:

```python
router = APIRouter(prefix="/api/reports", tags=["Reports"])

@router.get("/summary", response_model=ReportSummaryResponse)
def report_summary(
    period: str = Query(default="month"),
    start: datetime | None = Query(default=None),
    end: datetime | None = Query(default=None),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
):
    # custom range → validate start < end (else 422)
    # named period → parse_period_arg(period, ZoneInfo(current_user.timezone))
    # invalid named period → 422
    return get_report_summary(db, current_user.id, start_date=..., end_date=...)
```

Then register in `backend/app/main.py` — add `reports` to the
`from app.api import (...)` block and `app.include_router(reports.router)`.
No migration needed (read-only).

---

## Step 3 — Telegram `/report` handler (US-17)

In `backend/app/core/telegram_service.py`, add a new section (before the
natural-language branch, after `/cancel`):

```python
if text.startswith("/report"):
    parts = text.split(maxsplit=1)
    arg = parts[1].strip() if len(parts) > 1 else ""
    user = db.get(User, user_id)
    tz_str = getattr(user, "timezone", None) if user else None
    tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
    start, end = parse_period_arg(arg, tz)
    summary = get_report_summary(db, user_id, start_date=start, end_date=end)
    return _format_report(summary, period_label(arg))
```

- Add a `_format_report(summary, label)` helper that renders:
  `📊 Report — {label}` / `📈 Income` / `📉 Expense` / `Net` / `By category` lines.
- New imports: `from zoneinfo import ZoneInfo`,
  `from app.core.report_service import get_report_summary, parse_period_arg, period_label`,
  `from app.schemas.report import ReportSummaryResponse`.
- **No LLM call** — reports are pure DB reads.

---

## Step 4 — Tests

### 4.1 `tests/test_report_service.py`
- Unit: `parse_period_arg` boundaries for every keyword + default + normalization
  (`"bulan ini"` == `"bulan-ini"`); `period_label` for all keywords.
- Integration (real `SessionLocal`, like `test_category_locked.py`): seed a user +
  categories + account + transactions with fixed `transaction_date` values, then
  assert `get_report_summary` totals & per-category breakdown match hand-computed
  numbers; out-of-period rows excluded; empty period → zeros; largest category first.

### 4.2 `tests/test_reports_api.py` (TestClient)
- 401 without token; default month returns zeros; all valid periods 200; invalid
  period 422; custom range 200; inverted range 422.

### 4.3 `tests/test_telegram_service.py` (add `/report` cases)
- Requires link; default period → "this month"; `minggu ini` → "this week";
  user timezone resolved via `db.get(User, ...)`.

> ⚠️ The Docker image bakes source **and** tests — after editing tests, run
> `docker compose up -d --build backend` before `pytest`.

---

## Step 5 — Verification (checkpoint)

```bash
cd backend
ruff check app/ tests/ --no-cache && black --check app/ tests/
docker compose up -d --build backend
docker compose exec -T backend pytest -q tests/
```

Expected: lint/format clean; **88 passed** (66 Phase 2 + 22 new Phase 3).

### Manual E2E (live service)
- Register → login → create account (expect 201) → create income + expense this
  month + one expense last month.
- `GET /api/reports/summary` → correct month totals + per-category rows;
  `?period=last-month` → only the old expense; `?period=bogus` → 422.
- Telegram: `process_telegram_update(db, {…text:"/report"})` → formatted summary;
  `/report bulan lalu` → zeros.

### Negative cases
- Invalid period → 422; `start >= end` → 422.
- Unlinked Telegram user → "not linked yet".

### Data check
- Report endpoints are read-only — no new rows, no migration.

---

## Done — move to Phase 4
When `task.md`'s Phase-3 items are all `[x]`, update:
1. `IMPLEMENTATION_PLAN.md` → move Phase 3 to Completed, make **Phase 4** current,
   fill its Goal/Open Questions/Changes/Verification from the roadmap.
2. `task.md` → move Phase 3 to Done, unmute Phase 4 items.
3. `walkthrough.md` → replace Phase-3 steps with Phase-4 steps
   (Kotlin + Compose Android app, MVVM, auth, transactions list, report charts).
