"""
report_service.py — aggregation queries for financial reports (US-16, US-17).

Rules per DATABASE.md §3.4:
- All aggregation (SUM, GROUP BY) done in PostgreSQL, NOT Python.
- Never pull raw transaction rows to app and sum in Python.
- Returns structured data consumed by both Android (REST) and Telegram (/report command).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from decimal import Decimal

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.models import Category, Transaction

logger = structlog.get_logger(__name__)


async def get_summary(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: datetime,
    date_to: datetime,
) -> dict:
    """
    Return income, expense, balance, and per-category breakdown for a given period.
    All aggregation done in one SQL query per CODING_RULES.md §2.3.
    """
    # Single query: sum income and expense totals + per-category breakdown
    cat_breakdown_stmt = (
        select(
            Category.name,
            Transaction.type,
            func.sum(Transaction.total_amount).label("total"),
        )
        .join(Category, Category.id == Transaction.category_id)
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= date_from,
                Transaction.transaction_date <= date_to,
            )
        )
        .group_by(Category.name, Transaction.type)
        .order_by(func.sum(Transaction.total_amount).desc())
    )

    result = await db.execute(cat_breakdown_stmt)
    rows = result.all()

    total_income = Decimal("0")
    total_expense = Decimal("0")
    income_categories: list[dict] = []
    expense_categories: list[dict] = []

    for row in rows:
        amount = Decimal(str(row.total))
        entry = {"category": row.name, "total": amount}
        if row.type == "income":
            total_income += amount
            income_categories.append(entry)
        else:
            total_expense += amount
            expense_categories.append(entry)

    return {
        "period": {"from": date_from.isoformat(), "to": date_to.isoformat()},
        "total_income": total_income,
        "total_expense": total_expense,
        "balance": total_income - total_expense,
        "income_by_category": income_categories,
        "expense_by_category": expense_categories,
    }


async def get_daily_trend(
    db: AsyncSession,
    user_id: uuid.UUID,
    date_from: datetime,
    date_to: datetime,
) -> list[dict]:
    """
    Return daily income/expense totals for chart rendering (bar/line chart in Android).
    """
    stmt = (
        select(
            func.date_trunc("day", Transaction.transaction_date).label("day"),
            Transaction.type,
            func.sum(Transaction.total_amount).label("total"),
        )
        .where(
            and_(
                Transaction.user_id == user_id,
                Transaction.transaction_date >= date_from,
                Transaction.transaction_date <= date_to,
            )
        )
        .group_by("day", Transaction.type)
        .order_by("day")
    )

    result = await db.execute(stmt)
    rows = result.all()

    # Pivot per day
    days: dict[str, dict] = {}
    for row in rows:
        day_key = row.day.date().isoformat()
        if day_key not in days:
            days[day_key] = {"date": day_key, "income": Decimal("0"), "expense": Decimal("0")}
        days[day_key][row.type] += Decimal(str(row.total))

    return list(days.values())


def format_report_text(summary: dict) -> str:
    """
    Format report as plain text for Telegram /report command.
    Concise, informative — no marketing fluff per DESIGN.md §7.
    """
    from_date = summary["period"]["from"][:10]
    to_date = summary["period"]["to"][:10]

    lines = [
        f"Laporan {from_date} — {to_date}",
        f"Pemasukan:  Rp{summary['total_income']:>12,.0f}",
        f"Pengeluaran: Rp{summary['total_expense']:>11,.0f}",
        f"Selisih:    Rp{summary['balance']:>12,.0f}",
        "",
        "Per kategori (pengeluaran):",
    ]
    for cat in summary["expense_by_category"]:
        lines.append(f"  {cat['category']:<20} Rp{cat['total']:>10,.0f}")

    return "\n".join(lines)
