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

`action='update'` covers an edit of an already-parsed draft (also LLM-parsed),
which must pass the same confirmation gate as new transactions.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from typing import Literal

import structlog
from sqlalchemy import delete, select
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

# Prefix `raw_input` untuk pending hasil fitur "Matching Mutasi" — dipakai
# `purge_matching_pendings()` agar pembersihan tidak menyentuh pending yang
# berasal dari jalur lain (mis. sisa baris historis bot Telegram).
MATCHING_MUTASI_RAW_PREFIX = "Matching Mutasi"


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
    account_id: uuid.UUID | None = None,
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
        account_id=account_id,
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


def purge_expired_pendings(db: Session, user_id: uuid.UUID | None = None) -> int:
    """Delete pending rows whose `expires_at` has passed — table hygiene.

    A pending row is a short-lived staging area: once it expires it can never be
    confirmed (`_get_pending_or_raise` refuses it), so keeping it only makes the
    table grow without bound. Called on every pending listing and at startup.

    `user_id=None` purges every user (maintenance); passing a user id scopes the
    purge to that user's rows.
    """
    now = datetime.now(UTC)
    stmt = delete(PendingTransaction).where(
        PendingTransaction.expires_at.is_not(None),
        PendingTransaction.expires_at <= now,
    )
    if user_id is not None:
        stmt = stmt.where(PendingTransaction.user_id == user_id)

    deleted = int(db.execute(stmt).rowcount or 0)
    db.commit()
    if deleted:
        log.info(
            "pending_expired_purged",
            user_id=str(user_id) if user_id else "*",
            deleted=deleted,
        )
    return deleted


def purge_matching_pendings(db: Session, user_id: uuid.UUID) -> int:
    """Delete unconfirmed "Matching Mutasi" pendings for one user.

    Matched rows are already stored as real transactions, so a pending row is
    only an unconfirmed leftover of a previous upload. When the user uploads a
    new statement the old leftover is superseded — dropping it keeps
    `pending_transactions` from accumulating rows nobody will ever confirm.

    Scoped to `raw_input` starting with `MATCHING_MUTASI_RAW_PREFIX` so pendings
    produced by other flows are never touched.
    """
    stmt = delete(PendingTransaction).where(
        PendingTransaction.user_id == user_id,
        PendingTransaction.raw_input.is_not(None),
        PendingTransaction.raw_input.startswith(MATCHING_MUTASI_RAW_PREFIX),
    )
    # Hapus tanpa commit: pemanggil menggabungkannya dengan transaksi lain
    # (pembuatan pending baru) dalam satu commit.
    deleted = int(db.execute(stmt).rowcount or 0)
    if deleted:
        log.info("pending_matching_purged", user_id=str(user_id), deleted=deleted)
    return deleted


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
        account_id = pending.account_id
        if account_id is None:
            account_id = get_or_create_default_account(db, user_id).id
        transaction = create_transaction_internal(
            db=db,
            user_id=user_id,
            type=pending.type,  # type: ignore[arg-type]
            total_amount=pending.total_amount,
            category_id=pending.category_id,
            account_id=account_id,
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
