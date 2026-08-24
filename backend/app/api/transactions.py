"""
Transactions API routes.

GET    /api/transactions         — list (cursor-based pagination, newest first)
POST   /api/transactions         — create a manual transaction (with optional items)
GET    /api/transactions/{id}    — get a single transaction with its items
PUT    /api/transactions/{id}    — update a transaction (replaces items if provided)
DELETE /api/transactions/{id}    — hard-delete a transaction

Cursor-based pagination:
  Each response includes `next_cursor` (ISO timestamp of the last item's created_at).
  To fetch the next page, pass `?cursor=<next_cursor>`.
  This is stable: new inserts don't shift page boundaries.
"""

import uuid
from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_db, require_active_user
from app.core.transaction_service import (
    create_transaction_internal,
    delete_transaction_internal,
    update_transaction_internal,
)
from app.models.account import Account
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.transaction import (
    TransactionCreateRequest,
    TransactionListResponse,
    TransactionResponse,
    TransactionUpdateRequest,
)

router = APIRouter(prefix="/api/transactions", tags=["Transactions"])

_PAGE_SIZE = 20


def _verify_category_and_account(
    category_id: uuid.UUID,
    account_id: uuid.UUID,
    user_id: uuid.UUID,
    db: Session,
) -> None:
    """
    Validate that both category and account exist and are accessible by this user.
    Categories can be global (user_id=None) or user-specific.
    """
    from sqlalchemy import or_

    category = db.scalar(
        select(Category).where(
            Category.id == category_id,
            Category.is_active == True,  # noqa: E712
            or_(Category.user_id == None, Category.user_id == user_id),  # noqa: E711
        )
    )
    if category is None:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Category not found or not accessible",
        )

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


@router.get("", response_model=TransactionListResponse)
def list_transactions(
    cursor: str | None = Query(default=None, description="ISO timestamp of last seen item"),
    type: Literal["income", "expense"] | None = Query(default=None),
    category_id: uuid.UUID | None = Query(default=None),
    account_id: uuid.UUID | None = Query(default=None),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> TransactionListResponse:
    """
    List transactions newest-first with cursor-based pagination.
    Supports optional filtering by type, category, and account.
    """
    # Count total for UI (runs before cursor filter)
    count_stmt = select(func.count()).where(Transaction.user_id == current_user.id)
    if type:
        count_stmt = count_stmt.where(Transaction.type == type)
    if category_id:
        count_stmt = count_stmt.where(Transaction.category_id == category_id)
    if account_id:
        count_stmt = count_stmt.where(Transaction.account_id == account_id)
    total_count = db.scalar(count_stmt) or 0

    # Main query
    stmt = (
        select(Transaction)
        .where(Transaction.user_id == current_user.id)
        .options(selectinload(Transaction.items))
        .order_by(Transaction.transaction_date.desc(), Transaction.created_at.desc())
        .limit(_PAGE_SIZE + 1)  # fetch one extra to determine if there's a next page
    )

    if type:
        stmt = stmt.where(Transaction.type == type)
    if category_id:
        stmt = stmt.where(Transaction.category_id == category_id)
    if account_id:
        stmt = stmt.where(Transaction.account_id == account_id)

    # Apply cursor: filter to transactions older than the cursor timestamp
    if cursor:
        try:
            cursor_dt = datetime.fromisoformat(cursor)
            stmt = stmt.where(Transaction.transaction_date <= cursor_dt)
        except ValueError:
            pass  # invalid cursor is silently ignored — returns from beginning

    rows = list(db.scalars(stmt))

    has_next = len(rows) > _PAGE_SIZE
    page_items = rows[:_PAGE_SIZE]

    next_cursor = page_items[-1].transaction_date.isoformat() if has_next and page_items else None

    return TransactionListResponse(
        items=page_items,
        next_cursor=next_cursor,
        total_count=total_count,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
def create_transaction(
    body: TransactionCreateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Transaction:
    """
    Create a manual transaction with optional line items.
    Source is set to 'app' for transactions created via the REST API.
    All mutations are delegated to the service layer (CODING_RULES §2.1).
    """
    _verify_category_and_account(body.category_id, body.account_id, current_user.id, db)

    return create_transaction_internal(
        db=db,
        user_id=current_user.id,
        type=body.type,
        total_amount=body.total_amount,
        category_id=body.category_id,
        account_id=body.account_id,
        source="app",
        note=body.note,
        merchant=body.merchant.strip() if body.merchant else None,
        transaction_date=body.transaction_date,
        items=[item.model_dump() for item in body.items],
    )


@router.get("/{transaction_id}", response_model=TransactionResponse)
def get_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
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
def update_transaction(
    transaction_id: uuid.UUID,
    body: TransactionUpdateRequest,
    current_user: User = Depends(require_active_user),
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

    if body.category_id is not None or body.account_id is not None:
        _verify_category_and_account(
            body.category_id or transaction.category_id,
            body.account_id or transaction.account_id,
            current_user.id,
            db,
        )

    # Resolve PATCH semantics into final values, then delegate to the service
    # layer (CODING_RULES §2.1). `items` stays None to keep existing items
    # unless the caller explicitly provided a new list.
    return update_transaction_internal(
        db=db,
        transaction=transaction,
        type=body.type if body.type is not None else transaction.type,
        total_amount=(
            body.total_amount if body.total_amount is not None else transaction.total_amount
        ),
        category_id=body.category_id or transaction.category_id,
        account_id=body.account_id or transaction.account_id,
        note=body.note if body.note is not None else transaction.note,
        merchant=(
            body.merchant.strip() or None if body.merchant is not None else transaction.merchant
        ),
        transaction_date=body.transaction_date or transaction.transaction_date,
        items=[item.model_dump() for item in body.items] if body.items is not None else None,
    )


@router.delete("/{transaction_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_transaction(
    transaction_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
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
