"""
accounts.py — REST endpoints for account management (US-18 to US-22).
"""
import uuid
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_dep
from app.core import account_service
from app.db.session import get_db
from app.models.models import User
from app.schemas.schemas import (
    AccountCreateRequest,
    AccountUpdateRequest,
    AccountDeactivateRequest,
    AccountResponse,
)

router = APIRouter(prefix="/accounts", tags=["Accounts"])


@router.get("", response_model=list[AccountResponse])
async def list_accounts(
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> list[AccountResponse]:
    accounts = await account_service.list_accounts(db, current_user.id)
    return [AccountResponse.model_validate(a) for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
async def create_account(
    payload: AccountCreateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    try:
        acc = await account_service.create_account(db, current_user.id, payload, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return AccountResponse.model_validate(acc)


@router.get("/{account_id}", response_model=AccountResponse)
async def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    try:
        acc = await account_service.get_account(db, current_user.id, account_id)
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail=str(exc))
    return AccountResponse.model_validate(acc)


@router.patch("/{account_id}", response_model=AccountResponse)
async def update_account(
    account_id: uuid.UUID,
    payload: AccountUpdateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> AccountResponse:
    try:
        acc = await account_service.update_account(db, current_user.id, account_id, payload, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
    return AccountResponse.model_validate(acc)


@router.post("/{account_id}/deactivate", status_code=status.HTTP_204_NO_CONTENT)
async def deactivate_account(
    account_id: uuid.UUID,
    payload: AccountDeactivateRequest,
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> None:
    try:
        await account_service.deactivate_account(db, current_user.id, account_id, payload, source="app")
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))
