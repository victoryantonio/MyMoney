"""
Transactions API routes.

GET    /api/transactions         — list (keyset pagination; sortable)
POST   /api/transactions         — create a manual transaction (with optional items)
GET    /api/transactions/{id}    — get a single transaction with its items
PUT    /api/transactions/{id}    — update a transaction (replaces items if provided)
DELETE /api/transactions/{id}    — hard-delete a transaction

Keyset (cursor-based) pagination — DATABASE.md §3.2:
  The default sort is (transaction_date DESC, id DESC); the cursor encodes
  the last seen row as "{transaction_date_iso}|{id}". For amount sorts the
  cursor is "{total_amount}|{id}". The next page fetches rows strictly
  before/after that keyset, so inserts don't shift page boundaries and ties
  on the primary sort key are broken by id (no skips/duplicates).
  Legacy cursors (a bare ISO timestamp) are still accepted for date sorts.
"""

import uuid
from datetime import datetime
from decimal import Decimal
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

_SORT_MODES = Literal["newest", "oldest", "largest", "smallest"]

# Stable keyset ordering per sort mode: primary key desc/asc, then id as
# tie-breaker. Must stay in sync with _encode_cursor / _apply_cursor.
_SORT_ORDER = {
    "newest": (Transaction.transaction_date.desc(), Transaction.id.desc()),
    "oldest": (Transaction.transaction_date.asc(), Transaction.id.asc()),
    "largest": (Transaction.total_amount.desc(), Transaction.id.desc()),
    "smallest": (Transaction.total_amount.asc(), Transaction.id.asc()),
}


def _encode_cursor(tx: Transaction, sort: _SORT_MODES = "newest") -> str:
    """
    Encode the last seen row's keyset as '{sort_key}|{id}'.

    - date sorts (newest/oldest): '{ISO transaction_date}|{id}'
    - amount sorts (largest/smallest): '{total_amount}|{id}'
    """
    if sort in ("largest", "smallest"):
        return f"{tx.total_amount}|{tx.id}"
    return f"{tx.transaction_date.isoformat()}|{tx.id}"


def _apply_cursor(stmt, cursor: str | None, sort: _SORT_MODES = "newest"):
    """
    Apply the keyset filter matching the requested ORDER BY so pagination is
    stable on ties (DATABASE.md §3.2):

    - newest:  (transaction_date, id) < (cursor_date, cursor_id)
    - oldest:  (transaction_date, id) > (cursor_date, cursor_id)
    - largest: (total_amount, id) < (cursor_amount, cursor_id)
    - smallest:(total_amount, id) > (cursor_amount, cursor_id)

    Legacy cursors (a bare ISO timestamp, no '|') are accepted only for date
    sorts (transaction_date <= ts); for amount sorts a mismatched cursor is
    silently ignored so the client restarts from the beginning.
    """
    if not cursor:
        return stmt
    parts = cursor.split("|")
    try:
        if sort in ("largest", "smallest"):
            if len(parts) != 2:
                return stmt  # legacy date-only cursor is meaningless here
            cursor_amount = Decimal(parts[0])
            cursor_id = uuid.UUID(parts[1])
            if sort == "largest":
                return stmt.where(
                    tuple_(Transaction.total_amount, Transaction.id) < (cursor_amount, cursor_id)
                )
            return stmt.where(
                tuple_(Transaction.total_amount, Transaction.id) > (cursor_amount, cursor_id)
            )
        cursor_dt = datetime.fromisoformat(parts[0])
        if len(parts) == 2:
            cursor_id = uuid.UUID(parts[1])
            if sort == "oldest":
                return stmt.where(
                    tuple_(Transaction.transaction_date, Transaction.id) > (cursor_dt, cursor_id)
                )
            return stmt.where(
                tuple_(Transaction.transaction_date, Transaction.id) < (cursor_dt, cursor_id)
            )
        # Legacy: timestamp-only cursor.
        return stmt.where(Transaction.transaction_date <= cursor_dt)
    except (ValueError, TypeError, AttributeError, ArithmeticError):
        # Invalid cursor is silently ignored — returns from beginning.
        # ArithmeticError covers decimal.InvalidOperation (Decimal('abc')).
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
        description="Keyset of last seen item: '{ISO transaction_date}|{id}' "
        "(date sorts) or '{total_amount}|{id}' (amount sorts)",
    ),
    sort: _SORT_MODES = Query(
        default="newest",
        description="Sort order: newest|oldest|largest|smallest",
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
    List transactions with keyset pagination and server-side sorting
    (DATABASE.md §3.2). Supports optional filtering by type, category,
    account, and date range. `sort` selects the stable ordering:
    newest/oldest (by transaction_date) or largest/smallest (by total_amount).
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

    # Main query — keyset order per sort (see _SORT_ORDER)
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .options(selectinload(Transaction.items))
        .order_by(*_SORT_ORDER[sort])
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

    stmt = _apply_cursor(stmt, cursor, sort)

    rows = list(db.scalars(stmt))

    has_next = len(rows) > _PAGE_SIZE
    page_items = rows[:_PAGE_SIZE]

    next_cursor = (
        _encode_cursor(page_items[-1], sort) if has_next and page_items else None
    )

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
