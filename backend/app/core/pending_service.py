"""
Pending-confirmation service (CODING_RULES §2.4, REQUIREMENTS US-05/US-08).

LLM parse results are NEVER committed directly as a Transaction: they first land
in a `PendingTransaction` row. The user then either:

  * confirms  → the real Transaction is created/updated (audited) and the pending
                row is deleted — in ONE commit (transaction_service deletes the
                pending row before committing), so there is no crash window where
                both a Transaction and its pending row exist;
  * cancels   → the pending row is deleted, nothing is persisted (no audit row —
                no business action happened).

`action='update'` covers Telegram `/edit` (also LLM-parsed), which must pass the
same confirmation gate as new transactions.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.transaction_service import (
    create_transaction_internal,
    get_or_create_default_account,
    update_transaction_internal,
)
from app.models.pending_transaction import PendingTransaction
from app.models.transaction import Transaction

log = structlog.get_logger()

DEFAULT_EXPIRES_MINUTES = 10


def create_pending_transaction(
    db: Session,
    *,
    user_id: uuid.UUID,
    type: Literal["income", "expense"],
    total_amount: Decimal,
    category_id: uuid.UUID,
    source: str,
    action: Literal["create", "update"] = "create",
    note: str | None = None,
    merchant: str | None = None,
    confidence: str | None = None,
    raw_input: str | None = None,
    items: list[dict] | None = None,
    target_transaction_id: uuid.UUID | None = None,
    expires_minutes: int = DEFAULT_EXPIRES_MINUTES,
) -> PendingTransaction:
    """Persist an LLM parse result awaiting user confirmation."""
    if action not in ("create", "update"):
        raise ValueError("invalid pending action")
    if action == "update" and target_transaction_id is None:
        raise ValueError("action='update' requires target_transaction_id")

    pending = PendingTransaction(
        id=uuid.uuid4(),
        user_id=user_id,
        action=action,
        type=type,
        total_amount=total_amount,
        category_id=category_id,
        source=source,
        note=note,
        merchant=merchant,
        confidence=confidence,
        raw_input=raw_input,
        items=items,
        target_transaction_id=target_transaction_id,
        expires_at=datetime.now(UTC) + timedelta(minutes=expires_minutes),
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)
    log.info("pending_created", user_id=str(user_id), action=action)
    return pending


def get_latest_active_pending(db: Session, user_id: uuid.UUID) -> PendingTransaction | None:
    """Most recent non-expired pending row for the user, or None."""
    now = datetime.now(UTC)
    return db.scalar(
        select(PendingTransaction)
        .where(
            PendingTransaction.user_id == user_id,
            (PendingTransaction.expires_at.is_(None)) | (PendingTransaction.expires_at > now),
        )
        .order_by(PendingTransaction.created_at.desc())
        .limit(1)
    )


def _get_pending_or_raise(
    db: Session, user_id: uuid.UUID, pending_id: uuid.UUID | None
) -> PendingTransaction:
    """Fetch the latest (or specific) pending row; expired rows are purged.

    Raises ValueError with a user-facing reason when there is nothing to confirm.
    """
    query = select(PendingTransaction).where(PendingTransaction.user_id == user_id)
    if pending_id is not None:
        query = query.where(PendingTransaction.id == pending_id)
    pending = db.scalar(query.order_by(PendingTransaction.created_at.desc()).limit(1))
    if pending is None:
        raise ValueError("no pending transaction found")
    if pending.expires_at is not None and datetime.now(UTC) > pending.expires_at:
        db.delete(pending)
        db.commit()
        raise ValueError("pending transaction expired")
    return pending


def confirm_pending_transaction(
    db: Session,
    user_id: uuid.UUID,
    pending_id: uuid.UUID | None = None,
    audit_ip_address: str | None = None,
) -> Transaction:
    """Confirm the pending row: apply it as a real Transaction (single commit).

    `action='update'` applies the parsed values onto the pending row's target
    transaction; `action='create'` builds a new Transaction.
    """
    pending = _get_pending_or_raise(db, user_id, pending_id)

    if pending.action == "update":
        target = db.get(Transaction, pending.target_transaction_id)
        if target is None:
            # Target was deleted meanwhile — drop the stale pending row.
            db.delete(pending)
            db.commit()
            raise ValueError("target transaction no longer exists")
        transaction = update_transaction_internal(
            db=db,
            transaction=target,
            type=pending.type,  # type: ignore[arg-type]
            total_amount=pending.total_amount,
            category_id=pending.category_id,
            note=pending.note,
            merchant=pending.merchant,
            items=pending.items,
            audit_ip_address=audit_ip_address,
            pending=pending,
        )
    else:
        account = get_or_create_default_account(db, user_id)
        transaction = create_transaction_internal(
            db=db,
            user_id=user_id,
            type=pending.type,  # type: ignore[arg-type]
            total_amount=pending.total_amount,
            category_id=pending.category_id,
            account_id=account.id,
            source=pending.source,
            note=pending.note,
            merchant=pending.merchant,
            confidence=pending.confidence,
            items=pending.items,
            audit_ip_address=audit_ip_address,
            pending=pending,
        )

    log.info("pending_confirmed", user_id=str(user_id), action=pending.action)
    return transaction


def cancel_pending_transaction(
    db: Session,
    user_id: uuid.UUID,
    pending_id: uuid.UUID | None = None,
) -> PendingTransaction:
    """Delete the pending row — nothing is persisted and no audit row is written."""
    pending = _get_pending_or_raise(db, user_id, pending_id)
    db.delete(pending)
    db.commit()
    log.info("pending_cancelled", user_id=str(user_id), action=pending.action)
    return pending
