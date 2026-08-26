"""
Accounts API routes.

GET    /api/accounts                        — list accounts (active only by default)
POST   /api/accounts                        — create a new account
GET    /api/accounts/{id}                   — get account detail with computed balance
PUT    /api/accounts/{id}                   — update account name or bank name
POST   /api/accounts/{id}/deactivate        — deactivate an account (NOT delete).
                                               Per ARCHITECTURE.md §4.4: remaining
                                               balance is moved to a target account
                                               via balancing transactions.

Accounts can never be hard-deleted — only deactivated (is_active=False).
Transactions are preserved for historical accuracy.

Balance computation:
  current_balance = initial_balance
                  + SUM(amount WHERE type='income')
                  - SUM(amount WHERE type='expense')

This is computed per-query per ARCHITECTURE.md — no stored balance field.
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.core.audit_service import record_audit
from app.core.transaction_service import get_or_create_category
from app.models.account import Account
from app.models.profile import Profile
from app.models.transaction import Transaction
from app.schemas.account import (
    AccountCreateRequest,
    AccountDeactivateRequest,
    AccountResponse,
    AccountUpdateRequest,
)

router = APIRouter(prefix="/api/accounts", tags=["Accounts"])


def _compute_balance(account: Account, db: Session) -> tuple[Decimal, Decimal]:
    """
    Compute (current_balance, net_balance) from initial_balance + transaction history.
    All income transactions are added; all expense transactions are subtracted.
    net_balance = income − expense (excludes initial_balance).
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

    delta = result or Decimal("0.00")
    return account.initial_balance + delta, delta


def _to_response(account: Account, db: Session) -> AccountResponse:
    current_balance, net_balance = _compute_balance(account, db)
    return AccountResponse(
        id=account.id,
        account_name=account.account_name,
        bank_name=account.bank_name,
        initial_balance=account.initial_balance,
        current_balance=current_balance,
        net_balance=net_balance,
        is_active=account.is_active,
        created_at=account.created_at,
    )


@router.get("", response_model=list[AccountResponse])
def list_accounts(
    include_inactive: bool = False,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> list[AccountResponse]:
    """
    List accounts for the current user, including computed balance.

    Active accounts are returned by default. Pass `include_inactive=true` to
    also include deactivated accounts (used by Accounts Management UI to show
    the "Nonaktif" section).
    """
    accounts = list(
        db.scalars(
            select(Account)
            .where(
                Account.user_id == current_user.id,
                (
                    Account.is_active.is_(True)
                    if not include_inactive
                    else Account.is_active.in_([True, False])
                ),
            )
            .order_by(Account.is_active.desc(), Account.created_at)
        )
    )
    return [_to_response(a, db) for a in accounts]


@router.post("", response_model=AccountResponse, status_code=status.HTTP_201_CREATED)
def create_account(
    body: AccountCreateRequest,
    current_user: Profile = Depends(require_active_user),
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
    current_user: Profile = Depends(require_active_user),
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
    current_user: Profile = Depends(require_active_user),
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


@router.post("/{account_id}/deactivate", response_model=AccountResponse)
def deactivate_account(
    account_id: uuid.UUID,
    body: AccountDeactivateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """
    Deactivate an account (ARCHITECTURE.md §4.4). Accounts are NEVER deleted —
    only marked is_active=False.

    If the account has a non-zero balance, the balance MUST be moved to a
    target account first:
      - one expense transaction on the source account,
      - one income transaction on the target account (same amount),
    so the ledger stays balanced and no money silently disappears.
    If the balance is zero, deactivation happens directly.

    When the balance is non-zero and no target is given, HTTP 400 is returned.
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

    balance, _net = _compute_balance(account, db)

    target: Account | None = None
    if body.target_account_id is not None:
        if body.target_account_id == account.id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Target account must be different from the source account",
            )
        target = db.scalar(
            select(Account).where(
                Account.id == body.target_account_id,
                Account.user_id == current_user.id,
                Account.is_active == True,  # noqa: E712
            )
        )
        if target is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Target account not found",
            )

    if balance != Decimal("0.00") and target is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="This account has a balance. Pick a target account to move it to.",
        )

    # Move the remaining balance via balancing transactions (§4.4).
    # Created inline (not via create_transaction_internal) so the whole
    # deactivation — transfer + flag + audit — commits atomically in ONE
    # transaction: no half-applied transfer on failure.
    if balance != Decimal("0.00") and target is not None:
        expense_cat = get_or_create_category(db, current_user.id, "Transfer", "expense")
        income_cat = get_or_create_category(db, current_user.id, "Transfer", "income")
        transfer_note = f"Saldo dipindah dari {account.account_name} ke {target.account_name}"
        now = datetime.now(UTC)

        for tx_type, tx_account, tx_category, tx_merchant in (
            ("expense", account, expense_cat, target.account_name),
            ("income", target, income_cat, account.account_name),
        ):
            transfer_tx = Transaction(
                id=uuid.uuid4(),
                user_id=current_user.id,
                type=tx_type,
                total_amount=balance,
                category_id=tx_category.id,
                account_id=tx_account.id,
                merchant=tx_merchant,
                source="app",
                note=transfer_note,
                transaction_date=now,
            )
            db.add(transfer_tx)

    account.is_active = False
    record_audit(
        db,
        user_id=current_user.id,
        action="update",
        entity_type="account",
        entity_id=account.id,
        old_value={"is_active": True},
        new_value={
            "is_active": False,
            "moved_balance": str(balance),
            "target_account_id": str(target.id) if target else None,
        },
        source="app",
        ip_address=None,
    )
    db.commit()
    db.refresh(account)
    return _to_response(account, db)
