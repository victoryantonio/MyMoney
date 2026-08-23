"""
Transaction service for centralizing business logic.
This ensures both the REST API and the Telegram Bot use the same exact logic.
"""

import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.transaction_item import TransactionItem


def get_or_create_default_account(db: Session, user_id: uuid.UUID) -> Account:
    """
    Get the oldest active account for a user.
    If none exists, create a default 'Cash' account.
    """
    account = db.scalar(
        select(Account)
        .where(Account.user_id == user_id, Account.is_active == True)  # noqa: E712
        .order_by(Account.created_at.asc())
        .limit(1)
    )

    if account is None:
        account = Account(
            id=uuid.uuid4(),
            user_id=user_id,
            account_name="Cash",
            initial_balance=Decimal("0.00"),
        )
        db.add(account)
        db.commit()
        db.refresh(account)

    return account


def get_or_create_category(
    db: Session, user_id: uuid.UUID, category_name: str, tx_type: str
) -> Category:
    """
    Find a category by name (case-insensitive, checking both global and user-specific).
    If not found, creates a new custom category for the user using the provided name.
    """
    from sqlalchemy import func, or_

    category = db.scalar(
        select(Category).where(
            Category.is_active == True,  # noqa: E712
            func.lower(Category.name) == category_name.lower(),
            or_(Category.user_id == None, Category.user_id == user_id),  # noqa: E711
        )
    )

    if category is None:
        category = Category(
            id=uuid.uuid4(),
            user_id=user_id,
            name=category_name.title(),
            type=tx_type,
            is_default=False,
        )
        db.add(category)
        db.commit()
        db.refresh(category)

    return category


def create_transaction_internal(
    db: Session,
    user_id: uuid.UUID,
    type: Literal["income", "expense"],
    total_amount: Decimal,
    category_id: uuid.UUID,
    account_id: uuid.UUID,
    source: str,
    note: str | None = None,
    merchant: str | None = None,
    transaction_date: datetime | None = None,
    confidence: str | None = None,
) -> Transaction:
    """Core logic for creating a transaction."""
    if transaction_date is None:
        transaction_date = datetime.now(timezone.utc)

    transaction = Transaction(
        id=uuid.uuid4(),
        user_id=user_id,
        type=type,
        total_amount=total_amount,
        category_id=category_id,
        account_id=account_id,
        merchant=merchant,
        source=source,
        note=note,
        transaction_date=transaction_date,
        confidence=confidence,
    )
    db.add(transaction)
    db.commit()
    db.refresh(transaction)
    return transaction


def update_transaction_internal(
    db: Session,
    transaction: Transaction,
    type: Literal["income", "expense"],
    total_amount: Decimal,
    category_id: uuid.UUID,
    note: str | None = None,
) -> Transaction:
    """Core logic for updating a transaction."""
    transaction.type = type
    transaction.total_amount = total_amount
    transaction.category_id = category_id
    transaction.note = note
    db.commit()
    db.refresh(transaction)
    return transaction
