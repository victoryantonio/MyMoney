"""
Integration tests for locked-category validation (CODING_RULES §2.9.D).

LLM-originated categories must NEVER be auto-created: unknown names resolve
to the seeded global "Other" category. Requires a running PostgreSQL
(CI provides it via the postgres service container).
"""

import uuid

import pytest
from sqlalchemy import func, select

from app.core.transaction_service import get_or_create_category
from app.db.session import SessionLocal
from app.models.category import Category
from app.models.user import User


@pytest.fixture
def db():
    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def user(db):
    u = User(
        id=uuid.uuid4(),
        email=f"cat_{uuid.uuid4().hex[:10]}@example.com",
        password_hash="x",
        display_name="Cat Test",
    )
    db.add(u)
    db.commit()
    db.refresh(u)
    return u


def _count_by_name(db, name: str, type: str) -> int:
    return db.scalar(
        select(func.count())
        .select_from(Category)
        .where(Category.name == name, Category.type == type)
    )


def test_unknown_expense_category_resolves_to_other(db, user):
    """LLM category 'ZzNotARealCategory' → global 'Other' (expense), no new row."""
    other = get_or_create_category(db, user.id, "ZzNotARealCategory", "expense", allow_create=False)
    assert other.name == "Other"
    assert other.type == "expense"
    assert other.user_id is None  # locked global default
    assert _count_by_name(db, "ZzNotARealCategory", "expense") == 0


def test_unknown_income_category_resolves_to_other(db, user):
    """Income variant resolves to the income 'Other' default, not the expense one."""
    other = get_or_create_category(db, user.id, "ZzMysteryIncome", "income", allow_create=False)
    assert other.name == "Other"
    assert other.type == "income"
    assert _count_by_name(db, "ZzMysteryIncome", "income") == 0


def test_known_global_category_matches_without_creation(db, user):
    """An existing seeded default (e.g. 'Food') matches and creates nothing."""
    before = _count_by_name(db, "Food", "expense")
    category = get_or_create_category(db, user.id, "food", "expense", allow_create=False)
    assert category.name == "Food"
    assert _count_by_name(db, "Food", "expense") == before


def test_allow_create_true_still_creates_custom(db, user):
    """Explicit user intent (REST path) still creates a custom category."""
    raw = f"custom{uuid.uuid4().hex[:6]}"
    name = raw.title()  # service normalizes via str.title()
    category = get_or_create_category(db, user.id, raw, "expense", allow_create=True)
    assert category.name == name
    assert category.user_id == user.id
    assert _count_by_name(db, name, "expense") == 1
