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

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import and_, case, func, or_, select
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.core.audit_service import record_audit
from app.core.rate_limit import limiter
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
    income → +, expense → −, transfer: saldo keluar dari akun asal (−),
    masuk ke akun tujuan (+). net_balance = income − expense (excludes
    initial_balance). Uses a single aggregate SQL query for efficiency.
    """
    result = db.execute(
        select(
            func.coalesce(
                func.sum(
                    Transaction.total_amount
                    * func.cast(
                        case(
                            (
                                and_(
                                    Transaction.type == "income",
                                    Transaction.account_id == account.id,
                                ),
                                1,
                            ),
                            (
                                and_(
                                    Transaction.type == "expense",
                                    Transaction.account_id == account.id,
                                ),
                                -1,
                            ),
                            (
                                and_(
                                    Transaction.type == "transfer",
                                    Transaction.account_id == account.id,
                                ),
                                -1,
                            ),
                            (
                                and_(
                                    Transaction.type == "transfer",
                                    Transaction.to_account_id == account.id,
                                ),
                                1,
                            ),
                            else_=0,
                        ),
                        Transaction.total_amount.type,
                    )
                ),
                Decimal("0.00"),
            )
        ).where(
            or_(
                Transaction.account_id == account.id,
                Transaction.to_account_id == account.id,
            )
        )
    ).scalar()

    delta = result or Decimal("0.00")
    # SUM over (Numeric(14,2) * cast) can widen the scale (e.g. 80000.0000).
    # Normalize to 2 decimals so API balances are consistent with NUMERIC(14,2).
    delta = delta.quantize(Decimal("0.01"))
    return (account.initial_balance + delta).quantize(Decimal("0.01")), delta


def _to_response(account: Account, db: Session) -> AccountResponse:
    current_balance, net_balance = _compute_balance(account, db)
    return AccountResponse(
        id=account.id,
        account_name=account.account_name,
        account_type=account.account_type,
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
@limiter.limit("20/minute")
def create_account(
    request: Request,
    body: AccountCreateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Create a new account (cash, e-wallet, or bank account)."""
    account = Account(
        id=uuid.uuid4(),
        user_id=current_user.id,
        account_name=body.account_name.strip(),
        account_type=body.account_type,
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
@limiter.limit("20/minute")
def update_account(
    request: Request,
    account_id: uuid.UUID,
    body: AccountUpdateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> AccountResponse:
    """Update account name or account type."""
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
    if body.account_type is not None:
        account.account_type = body.account_type
    if body.initial_balance is not None:
        account.initial_balance = body.initial_balance

    db.commit()
    db.refresh(account)
    return _to_response(account, db)


@router.post("/{account_id}/deactivate", response_model=AccountResponse)
@limiter.limit("20/minute")
def deactivate_account(
    request: Request,
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
      - satu transaksi transfer (type='transfer') dari akun sumber ke akun
        tujuan (jumlah sama),
    sehingga pembukuan tetap seimbang dan tidak ada uang yang hilang.
    Transfer netral di laporan pemasukan/pengeluaran.
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

    # Pindahkan sisa saldo lewat SATU transaksi transfer (type='transfer',
    # migrasi 0008): saldo keluar dari akun asal dan masuk ke akun tujuan —
    # netral di laporan income/expense. Dibuat inline (bukan via
    # create_transaction_internal) agar seluruh deaktivasi — transfer + flag
    # + audit — commit atomik dalam SATU transaksi.
    if balance != Decimal("0.00") and target is not None:
        transfer_note = f"Saldo dipindah dari {account.account_name} ke {target.account_name}"
        now = datetime.now(UTC)
        transfer_tx = Transaction(
            id=uuid.uuid4(),
            user_id=current_user.id,
            type="transfer",
            total_amount=balance,
            category_id=None,
            account_id=account.id,
            to_account_id=target.id,
            merchant=target.account_name,
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
