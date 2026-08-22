"""
transactions.py — REST endpoints for transaction CRUD.
API layer only: routing + request validation + response formatting.
All logic lives in transaction_service.
"""
import uuid
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_dep
from app.core import transaction_service
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    TransactionCreateRequest,
    TransactionResponse,
    TransactionUpdateRequest,
    CursorPage,
)

router = APIRouter(prefix="/transactions", tags=["Transactions"])


@router.get("", response_model=CursorPage)
async def list_transactions(
    cursor: str | None = Query(default=None),
    limit: int = Query(default=20, ge=1, le=100),
    category_id: uuid.UUID | None = Query(default=None),
    type: str | None = Query(default=None, pattern="^(income|expense)$"),
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> CursorPage:
    rows, next_cursor, has_more = await transaction_service.list_transactions(
        db,
        current_user.id,
        limit=limit,
        cursor=cursor,
        category_id=category_id,
        type_filter=type,
        date_from=date_from,
        date_to=date_to,
    )
    return CursorPage(
        data=[TransactionResponse.model_validate(t) for t in rows],
        next_cursor=next_cursor,
        has_more=has_more,
    )


@router.post("", response_model=TransactionResponse, status_code=status.HTTP_201_CREATED)
async def create_transaction(
    payload: TransactionCreateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    try:
        tx = await transaction_service.create_transaction(db, current_user.id, payload, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return TransactionResponse.model_validate(tx)


@router.get("/{tx_id}", response_model=TransactionResponse)
async def get_transaction(
    tx_id: uuid.UUID,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    try:
        tx = await transaction_service.get_transaction(db, current_user.id, tx_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return TransactionResponse.model_validate(tx)


@router.patch("/{tx_id}", response_model=TransactionResponse)
async def update_transaction(
    tx_id: uuid.UUID,
    payload: TransactionUpdateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> TransactionResponse:
    try:
        tx = await transaction_service.update_transaction(db, current_user.id, tx_id, payload, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return TransactionResponse.model_validate(tx)


@router.delete("/{tx_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_transaction(
    tx_id: uuid.UUID,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await transaction_service.delete_transaction(db, current_user.id, tx_id, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
