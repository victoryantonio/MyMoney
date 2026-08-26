"""
Integration tests for locked-category validation (CODING_RULES §2.9.D).

LLM-originated categories must NEVER be auto-created: unknown names resolve
to the seeded global "Other" category. Requires a running PostgreSQL
(CI provides it via the postgres service container).
"""

import uuid

from sqlalchemy import func, select

from app.core.transaction_service import get_or_create_category
from app.models.category import Category


def _count_by_name(db, name: str, type: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Category)
        .where(Category.name == name, Category.type == type)
    )


def test_unknown_expense_category_resolves_to_other(db, profile):
    """LLM category 'ZzNotARealCategory' → global 'Other' (expense), no new row."""
    other = get_or_create_category(
        db, profile.id, "ZzNotARealCategory", "expense", allow_create=False
    )
    assert other.name == "Other"
    assert other.type == "expense"
    assert other.user_id is None  # locked global default
    assert _count_by_name(db, "ZzNotARealCategory", "expense") == 0


def test_unknown_income_category_resolves_to_other(db, profile):
    """Income variant resolves to the income 'Other' default, not the expense one."""
    other = get_or_create_category(db, profile.id, "ZzMysteryIncome", "income", allow_create=False)
    assert other.name == "Other"
    assert other.type == "income"
    assert _count_by_name(db, "ZzMysteryIncome", "income") == 0


def test_known_global_category_matches_without_creation(db, profile):
    """An existing seeded default (e.g. 'Food') matches and creates nothing."""
    before = _count_by_name(db, "Food", "expense")
    category = get_or_create_category(db, profile.id, "food", "expense", allow_create=False)
    assert category.name == "Food"
    assert _count_by_name(db, "Food", "expense") == before


def test_allow_create_true_still_creates_custom(db, profile):
    """Explicit user intent (REST path) still creates a custom category."""
    raw = f"custom{uuid.uuid4().hex[:6]}"
    name = raw.title()  # service normalizes via str.title()
    category = get_or_create_category(db, profile.id, raw, "expense", allow_create=True)
    assert category.name == name
    assert category.user_id == profile.id
    assert _count_by_name(db, name, "expense") == 1
