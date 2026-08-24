"""
Transaction service for centralizing business logic.
This ensures both the REST API and the Telegram Bot use the same exact logic
and that every mutation is audited (CODING_RULES §2.6).
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal
from typing import Literal

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.core.audit_service import record_audit
from app.models.account import Account
from app.models.category import Category
from app.models.pending_transaction import PendingTransaction
from app.models.transaction import Transaction
from app.models.transaction_item import TransactionItem

# Names of locked default categories to fall back to (seeded in migration 0001).
DEFAULT_CATEGORY_OTHER = "Other"


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
    db: Session,
    user_id: uuid.UUID,
    category_name: str,
    tx_type: str,
    allow_create: bool = True,
) -> Category:
    """
    Find a category by name (case-insensitive, checking both global and
    user-specific).

    - allow_create=True (default): if not found, create a custom category.
    - allow_create=False (LLM paths — CODING_RULES §2.9.D): NEVER auto-create.
      Falls back to the locked default category "Other" of the matching type.
    """
    category = db.scalar(
        select(Category).where(
            Category.is_active == True,  # noqa: E712
            func.lower(Category.name) == category_name.lower(),
            or_(Category.user_id == None, Category.user_id == user_id),  # noqa: E711
        )
    )

    if category is not None:
        return category

    if allow_create:
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

    # Locked mode: resolve to the seeded default "Other" for the tx type.
    other = db.scalar(
        select(Category).where(
            Category.is_active == True,  # noqa: E712
            func.lower(Category.name) == DEFAULT_CATEGORY_OTHER.lower(),
            Category.type == tx_type,
            Category.user_id.is_(None),
        )
    )
    if other is None:
        raise ValueError(f"default category 'Other' ({tx_type}) is missing — re-run migration 0001")
    return other


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
    items: list[dict] | None = None,
    audit_ip_address: str | None = None,
    pending: PendingTransaction | None = None,
) -> Transaction:
    """Core logic for creating a transaction (audited).

    When `pending` is given (pending-confirmation flow), the pending row is
    deleted in the same commit — so confirming a pending parse never leaves a
    crash window where both the Transaction and its pending row exist.
    """
    if transaction_date is None:
        transaction_date = datetime.now(UTC)

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
    for item_data in items or []:
        transaction.items.append(
            TransactionItem(
                id=uuid.uuid4(),
                name=item_data["name"].strip(),
                qty=item_data["qty"],
                price=item_data["price"],
            )
        )
    db.add(transaction)
    record_audit(
        db,
        user_id=user_id,
        action="create",
        entity_type="transaction",
        entity_id=transaction.id,
        new_value={
            "type": type,
            "total_amount": str(total_amount),
            "category_id": str(category_id),
            "account_id": str(account_id),
            "source": source,
            "note": note,
        },
        source=source,
        ip_address=audit_ip_address,
    )
    if pending is not None:
        db.delete(pending)
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
    merchant: str | None = None,
    account_id: uuid.UUID | None = None,
    transaction_date: datetime | None = None,
    items: list[dict] | None = None,
    audit_ip_address: str | None = None,
    pending: PendingTransaction | None = None,
) -> Transaction:
    """Core logic for updating a transaction (audited).

    `items=None` keeps existing line items untouched; a list replaces them.
    When `pending` is given (pending-confirmation flow for LLM edits), the
    pending row is deleted in the same commit.
    """
    old_value = {
        "type": transaction.type,
        "total_amount": str(transaction.total_amount),
        "category_id": str(transaction.category_id),
        "account_id": str(transaction.account_id),
        "note": transaction.note,
        "merchant": transaction.merchant,
        "transaction_date": (
            transaction.transaction_date.isoformat() if transaction.transaction_date else None
        ),
    }
    transaction.type = type
    transaction.total_amount = total_amount
    transaction.category_id = category_id
    transaction.note = note
    if merchant is not None:
        transaction.merchant = merchant
    if account_id is not None:
        transaction.account_id = account_id
    if transaction_date is not None:
        transaction.transaction_date = transaction_date
    if items is not None:
        for item in list(transaction.items):
            db.delete(item)
        for item_data in items:
            transaction.items.append(
                TransactionItem(
                    id=uuid.uuid4(),
                    name=item_data["name"].strip(),
                    qty=item_data["qty"],
                    price=item_data["price"],
                )
            )
    record_audit(
        db,
        user_id=transaction.user_id,
        action="update",
        entity_type="transaction",
        entity_id=transaction.id,
        old_value=old_value,
        new_value={
            "type": type,
            "total_amount": str(total_amount),
            "category_id": str(category_id),
            "account_id": str(transaction.account_id),
            "note": note,
            "merchant": transaction.merchant,
        },
        source=transaction.source,
        ip_address=audit_ip_address,
    )
    if pending is not None:
        db.delete(pending)
    db.commit()
    db.refresh(transaction)
    return transaction


def delete_transaction_internal(
    db: Session,
    transaction: Transaction,
    audit_ip_address: str | None = None,
) -> None:
    """Soft-delete a transaction (audited). Items are deleted by cascade."""
    record_audit(
        db,
        user_id=transaction.user_id,
        action="delete",
        entity_type="transaction",
        entity_id=transaction.id,
        old_value={
            "type": transaction.type,
            "total_amount": str(transaction.total_amount),
            "category_id": str(transaction.category_id),
            "note": transaction.note,
        },
        source=transaction.source,
        ip_address=audit_ip_address,
    )
    db.delete(transaction)
    db.commit()
