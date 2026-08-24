"""
Accounts API routes.

GET    /api/accounts            — list all active accounts with computed current balance
POST   /api/accounts            — create a new account
GET    /api/accounts/{id}       — get account detail with current balance
PUT    /api/accounts/{id}       — update account name or bank name
DELETE /api/accounts/{id}       — soft-delete (is_active=False)

Balance computation:
  current_balance = initial_balance
                  + SUM(amount WHERE type='income')
                  - SUM(amount WHERE type='expense')

This is computed per-query per ARCHITECTURE.md — no stored balance field.
"""

import uuid
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.models.account import Account
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.account import AccountCreateRequest, AccountResponse, AccountUpdateRequest

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


def _compute_balance(account: Account, db: Session) -> Decimal:
    """
    Compute current balance from initial_balance + transaction history.
    All income transactions are added; all expense transactions are subtracted.
    Uses a single aggregate SQL query for efficiency.
    """
    result = db.execute(
        select(
            func.coalesce(
                func.sum(
                    Transaction.total_amount
                    * func.cast(
                        case(
                            (Transaction.type == "income", 1),
                            else_=-1,
                        ),
                        Transaction.total_amount.type,
                    )
                ),
                Decimal("0.00"),
            )
        ).where(Transaction.account_id == account.id)
    ).scalar()

    return account.initial_balance + (result or Decimal("0.00"))


def _to_response(account: Account, db: Session) -> AccountResponse:
    return AccountResponse(
        id=account.id,
        account_name=account.account_name,
        bank_name=account.bank_name,
        initial_balance=account.initial_balance,
        current_balance=_compute_balance(account, db),
        is_active=account.is_active,
        created_at=account.created_at,
    )


@router.get("", response_model=list[AccountResponse])
def list_accounts(
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    """List all active accounts for the current user, including computed balance."""
    accounts = list(
        db.scalars(
            select(Account)
            .where(Account.user_id == current_user.id, Account.is_active == True)  # noqa: E712
            .order_by(Account.created_at)
        )
    )
    return [_to_response(a, db) for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Create a new account (cash wallet or bank account)."""
    account = Account(
        id=uuid.uuid4(),
        user_id=current_user.id,
        account_name=body.account_name.strip(),
        bank_name=body.bank_name.strip() if body.bank_name else None,
        initial_balance=body.initial_balance,
    )
    db.add(account)
    db.commit()
    db.refresh(account)
    return _to_response(account, db)


@router.get("/{account_id}", response_model=AccountResponse)
def get_account(
    account_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Get a single account with its current computed balance."""
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.is_active == True,  # noqa: E712
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")
    return _to_response(account, db)


@router.put("/{account_id}", response_model=AccountResponse)
def update_account(
    account_id: uuid.UUID,
    body: AccountUpdateRequest,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Update account name or bank name."""
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.is_active == True,  # noqa: E712
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    if body.account_name is not None:
        account.account_name = body.account_name.strip()
    if body.bank_name is not None:
        account.bank_name = body.bank_name.strip() or None

    db.commit()
    db.refresh(account)
    return _to_response(account, db)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_account(
    account_id: uuid.UUID,
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> None:
    """
    Soft-delete an account. Existing transactions are preserved for historical accuracy.
    The account will no longer appear in listings.
    """
    account = db.scalar(
        select(Account).where(
            Account.id == account_id,
            Account.user_id == current_user.id,
            Account.is_active == True,  # noqa: E712
        )
    )
    if account is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Account not found")

    account.is_active = False
    db.commit()
