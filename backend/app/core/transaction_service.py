"""
transaction_service.py — CRUD for transactions (manual input, no LLM).

Rules per CODING_RULES.md §2.2–2.3:
- All DB access in this file, not in api/ layer.
- Pagination is cursor-based from the start (DATABASE.md §3.2).
- Eager loading via selectinload for transaction + items + category.
- Audit trail called explicitly on every mutation.
- Single function used by both Telegram bot and Android REST API.
"""
import base64
import json
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

import structlog
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit_service import log_action
from app.models.models import Account, Category, Transaction, TransactionItem
from app.schemas.schemas import TransactionCreateRequest, TransactionUpdateRequest

logger = structlog.get_logger(__name__)

# Cursor encodes (transaction_date ISO, id str) as base64 JSON
def _encode_cursor(transaction_date: datetime, tx_id: uuid.UUID) -> str:
    data = json.dumps({"d": transaction_date.isoformat(), "id": str(tx_id)})
    return base64.urlsafe_b64encode(data.encode()).decode()


def _decode_cursor(cursor: str) -> tuple[datetime, uuid.UUID]:
    data = json.loads(base64.urlsafe_b64decode(cursor.encode()).decode())
    return datetime.fromisoformat(data["d"]), uuid.UUID(data["id"])


async def _assert_category_owned(db: AsyncSession, user_id: uuid.UUID, category_id: uuid.UUID) -> Category:
    result = await db.execute(
        select(Category).where(
            Category.id == category_id,
            (Category.user_id == user_id) | (Category.user_id == None),
        )
    )
    cat = result.scalar_one_or_none()
    if not cat:
        raise ValueError("Kategori tidak ditemukan.")
    return cat


async def _assert_account_active(db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> Account:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id, Account.is_active == True)
    )
    acc = result.scalar_one_or_none()
    if not acc:
        raise ValueError("Akun tidak ditemukan atau tidak aktif.")
    return acc


async def list_transactions(
    db: AsyncSession,
    user_id: uuid.UUID,
    *,
    limit: int = 20,
    cursor: str | None = None,
    category_id: uuid.UUID | None = None,
    type_filter: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
) -> tuple[list[Transaction], str | None, bool]:
    """
    Return (transactions, next_cursor, has_more).
    Cursor-based pagination per DATABASE.md §3.2 — no OFFSET.
    """
    stmt = (
        select(Transaction)
        .options(selectinload(Transaction.items), selectinload(Transaction.category))
        .where(Transaction.user_id == user_id)
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(limit + 1)  # fetch +1 to detect has_more
    )

    if cursor:
        last_date, last_id = _decode_cursor(cursor)
        stmt = stmt.where(
            (Transaction.transaction_date < last_date)
            | and_(Transaction.transaction_date == last_date, Transaction.id < last_id)
        )

    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if type_filter:
        stmt = stmt.where(Transaction.type == type_filter)
    if date_from:
        stmt = stmt.where(Transaction.transaction_date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.transaction_date <= date_to)

    result = await db.execute(stmt)
    rows = list(result.scalars().all())

    has_more = len(rows) > limit
    if has_more:
        rows = rows[:limit]

    next_cursor = None
    if has_more and rows:
        last = rows[-1]
        next_cursor = _encode_cursor(last.transaction_date, last.id)

    return rows, next_cursor, has_more


async def get_transaction(db: AsyncSession, user_id: uuid.UUID, tx_id: uuid.UUID) -> Transaction:
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items), selectinload(Transaction.category))
        .where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise ValueError("Transaksi tidak ditemukan.")
    return tx


async def create_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    payload: TransactionCreateRequest,
    source: str,
    *,
    confidence: str | None = None,
    receipt_image_url: str | None = None,
) -> Transaction:
    """
    Create a committed transaction.
    Used by both REST API (manual input) and Telegram (after user confirmation).
    Single function — no duplicate logic per CODING_RULES.md §2.2.
    """
    await _assert_category_owned(db, user_id, payload.category_id)
    await _assert_account_active(db, user_id, payload.account_id)

    tx = Transaction(
        user_id=user_id,
        type=payload.type,
        total_amount=payload.total_amount,
        category_id=payload.category_id,
        account_id=payload.account_id,
        merchant=payload.merchant,
        note=payload.note,
        source=source,
        confidence=confidence,
        receipt_image_url=receipt_image_url,
        transaction_date=payload.transaction_date,
    )
    db.add(tx)
    await db.flush()

    if payload.items:
        items = [
            TransactionItem(
                transaction_id=tx.id,
                name=item.name,
                qty=item.qty,
                price=item.price,
            )
            for item in payload.items
        ]
        db.add_all(items)
        await db.flush()

    await log_action(
        db,
        user_id=user_id,
        action="create",
        entity_type="transaction",
        entity_id=tx.id,
        new_value={
            "type": tx.type,
            "total_amount": str(tx.total_amount),
            "category_id": str(tx.category_id),
            "source": source,
        },
        source=source,
    )

    # Reload with relationships for response
    await db.refresh(tx)
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items), selectinload(Transaction.category))
        .where(Transaction.id == tx.id)
    )
    tx = result.scalar_one()

    logger.info("transaction_created", user_id=str(user_id), tx_id=str(tx.id), amount=str(tx.total_amount))
    return tx


async def update_transaction(
    db: AsyncSession,
    user_id: uuid.UUID,
    tx_id: uuid.UUID,
    payload: TransactionUpdateRequest,
    source: str,
) -> Transaction:
    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items), selectinload(Transaction.category))
        .where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise ValueError("Transaksi tidak ditemukan.")

    old_snap = {
        "type": tx.type, "total_amount": str(tx.total_amount),
        "category_id": str(tx.category_id), "merchant": tx.merchant,
    }

    if payload.type is not None:
        tx.type = payload.type
    if payload.total_amount is not None:
        tx.total_amount = payload.total_amount
    if payload.category_id is not None:
        await _assert_category_owned(db, user_id, payload.category_id)
        tx.category_id = payload.category_id
    if payload.account_id is not None:
        await _assert_account_active(db, user_id, payload.account_id)
        tx.account_id = payload.account_id
    if payload.merchant is not None:
        tx.merchant = payload.merchant
    if payload.note is not None:
        tx.note = payload.note
    if payload.transaction_date is not None:
        tx.transaction_date = payload.transaction_date
    if payload.items is not None:
        # Replace all items
        for item in tx.items:
            await db.delete(item)
        await db.flush()
        new_items = [
            TransactionItem(transaction_id=tx.id, name=i.name, qty=i.qty, price=i.price)
            for i in payload.items
        ]
        db.add_all(new_items)

    tx.updated_at = datetime.now(timezone.utc)
    await db.flush()

    await log_action(
        db,
        user_id=user_id,
        action="update",
        entity_type="transaction",
        entity_id=tx.id,
        old_value=old_snap,
        new_value={"type": tx.type, "total_amount": str(tx.total_amount)},
        source=source,
    )

    result = await db.execute(
        select(Transaction)
        .options(selectinload(Transaction.items), selectinload(Transaction.category))
        .where(Transaction.id == tx.id)
    )
    tx = result.scalar_one()
    logger.info("transaction_updated", user_id=str(user_id), tx_id=str(tx_id))
    return tx


async def delete_transaction(
    db: AsyncSession, user_id: uuid.UUID, tx_id: uuid.UUID, source: str
) -> None:
    result = await db.execute(
        select(Transaction).where(Transaction.id == tx_id, Transaction.user_id == user_id)
    )
    tx = result.scalar_one_or_none()
    if not tx:
        raise ValueError("Transaksi tidak ditemukan.")

    old_snap = {"type": tx.type, "total_amount": str(tx.total_amount)}
    await db.delete(tx)
    await db.flush()

    await log_action(
        db,
        user_id=user_id,
        action="delete",
        entity_type="transaction",
        entity_id=tx_id,
        old_value=old_snap,
        source=source,
    )
    logger.info("transaction_deleted", user_id=str(user_id), tx_id=str(tx_id))
