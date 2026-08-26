"""
Tests for report_service.py (US-11, US-16, US-17).

Unit tests for period parsing (no DB) + integration tests for the SQL
aggregation against a real PostgreSQL (like test_category_locked.py).
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from zoneinfo import ZoneInfo

from app.core.report_service import (
    get_report_summary,
    get_report_trend,
    parse_period_arg,
    period_label,
)
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction

_TZ = ZoneInfo("UTC")

# ── Unit: parse_period_arg / period_label ────────────────────────────────────


class TestParsePeriod:
    def test_empty_defaults_to_this_month(self):
        start, end = parse_period_arg("", _TZ)
        assert start.day == 1 and start.hour == 0 and start.minute == 0
        assert end.day == 1 and end > start
        assert (end - start).days in (28, 29, 30, 31)

    def test_bulan_ini_keyword(self):
        start, end = parse_period_arg("bulan-ini", _TZ)
        assert start.day == 1 and end.day == 1

    def test_space_normalization(self):
        # "bulan ini" with a space normalizes to the same boundaries as "bulan-ini"
        a = parse_period_arg("bulan ini", _TZ)
        b = parse_period_arg("bulan-ini", _TZ)
        assert a == b

    def test_hari_ini(self):
        start, end = parse_period_arg("hari-ini", _TZ)
        assert start.hour == 0 and start.minute == 0
        assert end - start == timedelta(days=1)

    def test_today_english(self):
        assert parse_period_arg("today", _TZ) == parse_period_arg("hari-ini", _TZ)

    def test_minggu_ini_starts_monday(self):
        start, end = parse_period_arg("minggu-ini", _TZ)
        assert start.weekday() == 0  # Monday
        assert end - start == timedelta(days=7)

    def test_bulan_lalu(self):
        start, end = parse_period_arg("bulan-lalu", _TZ)
        assert start.day == 1 and end.day == 1
        assert (end - start).days in (28, 29, 30, 31)

    def test_period_labels(self):
        assert period_label("") == "this month"
        assert period_label("bulan ini") == "this month"
        assert period_label("hari-ini") == "today"
        assert period_label("minggu ini") == "this week"
        assert period_label("bulan lalu") == "last month"


# ── Integration: SQL aggregation on a real DB ────────────────────────────────


class TestReportAggregation:
    def _seed(self, db, profile):
        """Create categories, an account, and transactions with fixed dates.

        Categories are user-scoped (user_id=profile.id) so repeated test runs on
        the shared dev DB never pollute the global default set — the unique
        index idx_categories_user_name_type forbids duplicate globals.
        """
        food = Category(id=uuid.uuid4(), name="Food", type="expense", user_id=profile.id)
        transport = Category(id=uuid.uuid4(), name="Transport", type="expense", user_id=profile.id)
        salary = Category(id=uuid.uuid4(), name="Salary", type="income", user_id=profile.id)
        db.add_all([food, transport, salary])
        db.flush()

        account = Account(
            id=uuid.uuid4(), user_id=profile.id, account_name="Cash", initial_balance=Decimal("0")
        )
        db.add(account)
        db.flush()

        def tx(type_, amount, cat, when):
            db.add(
                Transaction(
                    id=uuid.uuid4(),
                    user_id=profile.id,
                    type=type_,
                    total_amount=Decimal(amount),
                    category_id=cat.id,
                    account_id=account.id,
                    source="app",
                    transaction_date=when,
                )
            )

        # August 2026 (UTC)
        tx("expense", "50000", food, datetime(2026, 8, 5, 10, 0, tzinfo=UTC))
        tx("expense", "25000", food, datetime(2026, 8, 20, 15, 30, tzinfo=UTC))
        tx("expense", "30000", transport, datetime(2026, 8, 12, 8, 0, tzinfo=UTC))
        tx("income", "1000000", salary, datetime(2026, 8, 1, 8, 0, tzinfo=UTC))
        # Outside the period — must be excluded
        tx("expense", "99999", food, datetime(2026, 7, 31, 23, 59, tzinfo=UTC))
        db.commit()
        return food, transport, salary

    def test_summary_totals_and_breakdown(self, db, profile):
        food, transport, salary = self._seed(db, profile)
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = datetime(2026, 9, 1, tzinfo=UTC)

        summary = get_report_summary(db, profile.id, start_date=start, end_date=end)

        assert summary.total_expense == Decimal("105000")  # 50000+25000+30000
        assert summary.total_income == Decimal("1000000")
        assert summary.net == Decimal("895000")

        by_name = {c.name: c for c in summary.categories}
        assert by_name["Food"].total == Decimal("75000")
        assert by_name["Food"].type == "expense"
        assert by_name["Transport"].total == Decimal("30000")
        assert by_name["Salary"].total == Decimal("1000000")
        assert by_name["Salary"].type == "income"

        # Bigger totals sort first
        assert summary.categories[0].name == "Salary"

    def test_summary_excludes_outside_period(self, db, profile):
        self._seed(db, profile)
        # July-only window → the single July transaction is the only match
        start = datetime(2026, 7, 1, tzinfo=UTC)
        end = datetime(2026, 8, 1, tzinfo=UTC)

        summary = get_report_summary(db, profile.id, start_date=start, end_date=end)

        assert summary.total_expense == Decimal("99999")
        assert summary.total_income == Decimal("0")

    def test_summary_empty_period(self, db, profile):
        start = datetime(2025, 1, 1, tzinfo=UTC)
        end = datetime(2025, 2, 1, tzinfo=UTC)

        summary = get_report_summary(db, profile.id, start_date=start, end_date=end)

        assert summary.total_expense == Decimal("0")
        assert summary.total_income == Decimal("0")
        assert summary.net == Decimal("0")
        assert summary.categories == []

    def test_aggregation_is_sql_not_python(self, db, profile):
        """Sanity check: the query returns GROUP BY rows (fewer than tx count)."""
        self._seed(db, profile)
        # 4 August transactions → 3 distinct (name, type) groups
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = datetime(2026, 9, 1, tzinfo=UTC)
        summary = get_report_summary(db, profile.id, start_date=start, end_date=end)
        assert len(summary.categories) == 3


class TestReportTrend:
    def _seed(self, db, profile):
        """Same seed as TestReportAggregation but with fixed UTC days."""
        food = Category(id=uuid.uuid4(), name="Food", type="expense", user_id=profile.id)
        salary = Category(id=uuid.uuid4(), name="Salary", type="income", user_id=profile.id)
        db.add_all([food, salary])
        db.flush()

        account = Account(
            id=uuid.uuid4(), user_id=profile.id, account_name="Cash", initial_balance=Decimal("0")
        )
        db.add(account)
        db.flush()

        def tx(type_, amount, cat, when):
            db.add(
                Transaction(
                    id=uuid.uuid4(),
                    user_id=profile.id,
                    type=type_,
                    total_amount=Decimal(amount),
                    category_id=cat.id,
                    account_id=account.id,
                    source="app",
                    transaction_date=when,
                )
            )

        tx("expense", "50000", food, datetime(2026, 8, 5, 10, 0, tzinfo=UTC))
        tx("expense", "25000", food, datetime(2026, 8, 20, 15, 30, tzinfo=UTC))
        tx("income", "1000000", salary, datetime(2026, 8, 1, 8, 0, tzinfo=UTC))
        tx("expense", "99999", food, datetime(2026, 7, 31, 23, 59, tzinfo=UTC))  # outside
        db.commit()

    def test_trend_buckets_by_day_and_zero_fills(self, db, profile):
        """Every day in range appears; income/expense bucketed per day."""
        self._seed(db, profile)
        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = datetime(2026, 9, 1, tzinfo=UTC)

        trend = get_report_trend(db, profile.id, start_date=start, end_date=end, tz=ZoneInfo("UTC"))

        # 31 days in August — all present (zero-filled)
        assert len(trend.points) == 31
        by_day = {p.date.isoformat(): p for p in trend.points}

        assert by_day["2026-08-01"].income == Decimal("1000000")
        assert by_day["2026-08-01"].expense == Decimal("0")
        assert by_day["2026-08-05"].expense == Decimal("50000")
        assert by_day["2026-08-20"].expense == Decimal("25000")
        # A quiet day is zero-filled, not omitted
        assert by_day["2026-08-10"].income == Decimal("0")
        assert by_day["2026-08-10"].expense == Decimal("0")
        # Day 31 exists and is zero-filled
        assert by_day["2026-08-31"].expense == Decimal("0")

    def test_trend_respects_timezone_boundaries(self, db, profile):
        """A transaction near midnight UTC lands on the right day in +07:00."""
        food = Category(id=uuid.uuid4(), name="Food", type="expense", user_id=profile.id)
        db.add(food)
        db.flush()
        account = Account(
            id=uuid.uuid4(), user_id=profile.id, account_name="Cash", initial_balance=Decimal("0")
        )
        db.add(account)
        db.flush()
        # 2026-08-05 20:00 UTC == 2026-08-06 03:00 WIB
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=profile.id,
                type="expense",
                total_amount=Decimal("10000"),
                category_id=food.id,
                account_id=account.id,
                source="app",
                transaction_date=datetime(2026, 8, 5, 20, 0, tzinfo=UTC),
            )
        )
        db.commit()

        start = datetime(2026, 8, 1, tzinfo=UTC)
        end = datetime(2026, 9, 1, tzinfo=UTC)
        trend = get_report_trend(
            db, profile.id, start_date=start, end_date=end, tz=ZoneInfo("Asia/Jakarta")
        )

        by_day = {p.date.isoformat(): p for p in trend.points}
        assert by_day["2026-08-05"].expense == Decimal("0")
        assert by_day["2026-08-06"].expense == Decimal("10000")
