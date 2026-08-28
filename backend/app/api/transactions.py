"""
Transactions API routes.

GET    /api/transactions         — list (keyset pagination, newest first)
POST   /api/transactions         — create a manual transaction (with optional items)
GET    /api/transactions/{id}    — get a single transaction with its items
PUT    /api/transactions/{id}    — update a transaction (replaces items if provided)
DELETE /api/transactions/{id}    — hard-delete a transaction

Keyset (cursor-based) pagination — DATABASE.md §3.2:
  Rows are ordered by (transaction_date DESC, id DESC); the cursor encodes
  the last seen row as "{transaction_date_iso}|{id}". The next page fetches
  rows strictly before that keyset, so inserts don't shift page boundaries
  and ties on transaction_date are broken by id (no skips/duplicates).
  Legacy cursors (a bare ISO timestamp) are still accepted.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select, tuple_
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_active_user
from app.core.rate_limit import limiter
from app.core.transaction_service import (
    create_transaction_internal,
    delete_transaction_internal,
    update_transaction_internal,
)
from app.models.account import Account
from app.models.category import Category, category_visible_clause
from app.models.profile import Profile
from app.models.transaction import Transaction
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

_PAGE_SIZE = 20


def _encode_cursor(tx: Transaction) -> str:
    """Encode the last seen row's keyset as '{iso_date}|{id}'."""
    return f"{tx.transaction_date.isoformat()}|{tx.id}"


def _apply_cursor(stmt, cursor: str | None):
    """
    Apply the keyset filter (transaction_date, id) < (cursor_date, cursor_id)
    — matching the ORDER BY so pagination is stable on ties (DATABASE.md §3.2).

    Legacy cursors (a bare ISO timestamp, no '|') fall back to the old
    transaction_date <= ts behaviour.
    """
    if not cursor:
        return stmt
    parts = cursor.split("|")
    try:
        cursor_dt = datetime.fromisoformat(parts[0])
        if len(parts) == 2:
            cursor_id = uuid.UUID(parts[1])
            return stmt.where(
                tuple_(Transaction.transaction_date, Transaction.id) < (cursor_dt, cursor_id)
            )
        # Legacy: timestamp-only cursor.
        return stmt.where(Transaction.transaction_date <= cursor_dt)
    except (ValueError, AttributeError):
        # Invalid cursor is silently ignored — returns from beginning.
        return stmt


def _verify_category_and_account(
    *,
    tx_type: str,
    category_id: uuid.UUID | None,
    account_id: uuid.UUID,
    to_account_id: uuid.UUID | None,
    user_id: uuid.UUID,
    db: Session,
) -> None:
    """
    Validate category/account references for a transaction, per type:

    - income/expense: category wajib (aktif & terlihat user) + akun asal.
    - transfer: TANPA kategori; akun asal + akun tujuan (aktif, milik user,
      dan berbeda).
    """
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == user_id,
            Account.is_active == True,  # noqa: E712
        )
    )
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Account not found or not accessible",
        )

    if tx_type == "transfer":
        if category_id is not None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Transfer transactions do not use a category",
            )
        if to_account_id is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target account is required for a transfer",
            )
        if to_account_id == account_id:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target account must be different from the source account",
            )
        target = db.scalar(
            select(Account).where(
                Account.id == to_account_id,
                Account.user_id == user_id,
                Account.is_active == True,  # noqa: E712
            )
        )
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Target account not found or not accessible",
            )
        return

    if category_id is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category is required for this transaction type",
        )
    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            category_visible_clause(user_id),
        )
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category not found or not accessible",
        )


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    cursor: str | None = Query(
        default=None,
        description="Keyset of last seen item: '{ISO transaction_date}|{id}'",
    ),
    type: Literal["income", "expense"] | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    date_from: datetime | None = Query(
        default=None,
        description="Only transactions on/after this date (inclusive)",
    ),
    date_to: datetime | None = Query(
        default=None,
        description="Only transactions on/before this date (inclusive)",
    ),
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    """
    List transactions newest-first with keyset pagination
    ((transaction_date, id) — DATABASE.md §3.2).
    Supports optional filtering by type, category, account, and date range.
    """
    # Count total for UI (runs before cursor filter)
    count_stmt = select(func.count()).where(Transaction.user_id == current_user.id)
    if type:
        count_stmt = count_stmt.where(Transaction.type == type)
    if category_id:
        count_stmt = count_stmt.where(Transaction.category_id == category_id)
    if account_id:
        count_stmt = count_stmt.where(Transaction.account_id == account_id)
    if date_from:
        count_stmt = count_stmt.where(Transaction.transaction_date >= date_from)
    if date_to:
        count_stmt = count_stmt.where(Transaction.transaction_date <= date_to)
    total_count = db.scalar(count_stmt) or 0

    # Main query — keyset order: (transaction_date DESC, id DESC)
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .options(selectinload(Transaction.items))
        .order_by(Transaction.transaction_date.desc(), Transaction.id.desc())
        .limit(_PAGE_SIZE + 1)  # fetch one extra to determine if there's a next page
    )

    if type:
        stmt = stmt.where(Transaction.type == type)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)
    if date_from:
        stmt = stmt.where(Transaction.transaction_date >= date_from)
    if date_to:
        stmt = stmt.where(Transaction.transaction_date <= date_to)

    stmt = _apply_cursor(stmt, cursor)

    rows = list(db.scalars(stmt))

    has_next = len(rows) > _PAGE_SIZE
    page_items = rows[:_PAGE_SIZE]

    next_cursor = _encode_cursor(page_items[-1]) if has_next and page_items else None

    return TransactionListResponse(
        items=page_items,
        next_cursor=next_cursor,
        total_count=total_count,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
@limiter.limit("30/minute")
def create_transaction(
    request: Request,
    body: TransactionCreateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Transaction:
    """
    Create a manual transaction with optional line items.
    Source is set to 'app' for transactions created via the REST API.
    All mutations are delegated to the service layer (CODING_RULES §2.1).
    """
    _verify_category_and_account(
        tx_type=body.type,
        category_id=body.category_id,
        account_id=body.account_id,
        to_account_id=body.to_account_id,
        user_id=current_user.id,
        db=db,
    )

    return create_transaction_internal(
        db=db,
        user_id=current_user.id,
        type=body.type,
        total_amount=body.total_amount,
        category_id=body.category_id,
        account_id=body.account_id,
        to_account_id=body.to_account_id,
        source="app",
        note=body.note,
        merchant=body.merchant.strip() if body.merchant else None,
        transaction_date=body.transaction_date,
        items=[item.model_dump() for item in body.items],
        original_currency=body.original_currency,
        exchange_rate=body.exchange_rate,
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: uuid.UUID,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Transaction:
    """Get a single transaction with all its line items."""
    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
        .options(selectinload(Transaction.items))
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")
    return transaction


@router.put("/{transaction_id}", response_model=TransactionResponse)
@limiter.limit("30/minute")
def update_transaction(
    request: Request,
    transaction_id: uuid.UUID,
    body: TransactionUpdateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Transaction:
    """
    Update a transaction. If `items` is provided, all existing items are replaced.
    Only the fields included in the body are updated (PATCH semantics via Optional fields).
    """
    transaction = db.scalar(
        select(Transaction)
        .where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
        .options(selectinload(Transaction.items))
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    new_type = body.type if body.type is not None else transaction.type
    new_account_id = body.account_id or transaction.account_id
    # Saat tipe berubah menjadi transfer, kategori HARUS di-null-kan — tidak
    # boleh jatuh ke kategori lama via PATCH fallback (transfer tanpa kategori).
    new_category_id = (
        None
        if new_type == "transfer"
        else (body.category_id if body.category_id is not None else transaction.category_id)
    )
    new_to_account_id = (
        body.to_account_id if body.to_account_id is not None else transaction.to_account_id
    )
    _verify_category_and_account(
        tx_type=new_type,
        category_id=new_category_id,
        account_id=new_account_id,
        to_account_id=new_to_account_id,
        user_id=current_user.id,
        db=db,
    )

    # Resolve PATCH semantics into final values, then delegate to the service
    # layer (CODING_RULES §2.1). `items` stays None to keep existing items
    # unless the caller explicitly provided a new list.
    return update_transaction_internal(
        db=db,
        transaction=transaction,
        type=new_type,
        total_amount=(
            body.total_amount if body.total_amount is not None else transaction.total_amount
        ),
        category_id=new_category_id,
        account_id=new_account_id,
        to_account_id=new_to_account_id,
        note=body.note if body.note is not None else transaction.note,
        merchant=(
            body.merchant.strip() or None if body.merchant is not None else transaction.merchant
        ),
        transaction_date=body.transaction_date or transaction.transaction_date,
        items=[item.model_dump() for item in body.items] if body.items is not None else None,
        original_currency=(
            body.original_currency
            if body.original_currency is not None
            else transaction.original_currency
        ),
        exchange_rate=(
            body.exchange_rate if body.exchange_rate is not None else transaction.exchange_rate
        ),
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
@limiter.limit("30/minute")
def delete_transaction(
    request: Request,
    transaction_id: uuid.UUID,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> None:
    """Hard-delete a transaction and all its items (CASCADE in DB)."""
    transaction = db.scalar(
        select(Transaction).where(
            Transaction.id == transaction_id,
            Transaction.user_id == current_user.id,
        )
    )
    if transaction is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Transaction not found")

    delete_transaction_internal(db, transaction)
