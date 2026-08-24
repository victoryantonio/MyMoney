"""
Report aggregation service (US-11, US-16, US-17).

All aggregation happens in SQL — `SUM`/`GROUP BY` — never in Python loops
(DATABASE.md §3.4). Postgres is far more efficient at this and it keeps the
backend light.

Period keywords supported by `parse_period_arg` (Indonesian + English):
  - hari-ini / today
  - minggu-ini / week / this-week
  - bulan-ini / month / this-month  (default when arg is empty)
  - bulan-lalu / last-month / previous-month
"""

from datetime import datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.category import Category
from app.models.transaction import Transaction
from app.schemas.report import CategoryTotal, ReportSummaryResponse

# ── Period parsing ────────────────────────────────────────────────────────────


def _normalize(arg: str | None) -> str:
    """Collapse whitespace and convert to kebab-case keywords."""
    return "-".join((arg or "").strip().lower().split())


def parse_period_arg(arg: str | None, tz: ZoneInfo) -> tuple[datetime, datetime]:
    """
    Parse a period keyword into an inclusive [start, end) boundary pair.

    - "hari-ini":     [today 00:00, tomorrow 00:00)
    - "minggu-ini":   [Monday 00:00, next Monday 00:00)
    - "bulan-lalu":   [first of previous month, first of this month)
    - default/empty:  [first of this month, first of next month)
    """
    now = datetime.now(tz)
    norm = _normalize(arg)

    if norm in ("hari-ini", "today"):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)
    elif norm in ("minggu-ini", "week", "this-week"):
        start = now.replace(hour=0, minute=0, second=0, microsecond=0) - timedelta(
            days=now.weekday()
        )
        end = start + timedelta(days=7)
    elif norm in ("bulan-lalu", "last-month", "previous-month"):
        first_of_this_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = first_of_this_month
        start = (first_of_this_month - timedelta(days=1)).replace(day=1)
    else:  # default: bulan-ini / month / this-month / anything unknown
        start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        end = (start + timedelta(days=32)).replace(day=1)
    return start, end


def period_label(arg: str | None) -> str:
    """Human-readable English label for a period keyword (for /report replies)."""
    norm = _normalize(arg)
    if norm in ("hari-ini", "today"):
        return "today"
    if norm in ("minggu-ini", "week", "this-week"):
        return "this week"
    if norm in ("bulan-lalu", "last-month", "previous-month"):
        return "last month"
    return "this month"


# ── Aggregation (SQL only) ────────────────────────────────────────────────────


def get_report_summary(
    db: Session,
    user_id,
    *,
    start_date: datetime,
    end_date: datetime,
) -> ReportSummaryResponse:
    """
    Return income/expense totals plus a per-category breakdown for the period.

    Boundaries are [start_date, end_date) — end_date is exclusive.
    """
    # Overall totals per type (one GROUP BY row per type)
    total_rows = db.execute(
        select(Transaction.type, func.sum(Transaction.total_amount))
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date,
        )
        .group_by(Transaction.type)
    ).all()
    totals: dict[str, Decimal] = {row[0]: Decimal(row[1]) for row in total_rows}
    total_income = totals.get("income", Decimal("0"))
    total_expense = totals.get("expense", Decimal("0"))

    # Per-category breakdown (biggest first)
    cat_rows = db.execute(
        select(Category.name, Transaction.type, func.sum(Transaction.total_amount))
        .join(Transaction, Transaction.category_id == Category.id)
        .where(
            Transaction.user_id == user_id,
            Transaction.transaction_date >= start_date,
            Transaction.transaction_date < end_date,
        )
        .group_by(Category.name, Transaction.type)
        .order_by(func.sum(Transaction.total_amount).desc())
    ).all()
    categories = [
        CategoryTotal(name=row[0], type=row[1], total=Decimal(row[2])) for row in cat_rows
    ]

    return ReportSummaryResponse(
        start_date=start_date,
        end_date=end_date,
        total_income=total_income,
        total_expense=total_expense,
        net=total_income - total_expense,
        categories=categories,
    )
