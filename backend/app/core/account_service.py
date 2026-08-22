"""
account_service.py — CRUD for accounts, computed balance, deactivation flow.

Key rules per CODING_RULES.md §2.8 and REQUIREMENTS.md US-18–US-22:
- Accounts are NEVER hard-deleted if they have transaction history (ON DELETE RESTRICT enforced at DB level).
- Deactivating an account with remaining balance creates a balancing transaction (does NOT edit historical data).
- Inactive accounts stay in historical reports, never appear in new transaction inputs.
- Balance is always computed (initial_balance + Σ transactions), never stored as a mutable field.
"""
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from typing import Sequence

import structlog
from sqlalchemy import select, func, case
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.audit_service import log_action
from app.models.models import Account, Transaction, Category
from app.schemas.schemas import AccountCreateRequest, AccountUpdateRequest, AccountDeactivateRequest

logger = structlog.get_logger(__name__)


async def _computed_balance(db: AsyncSession, account_id: uuid.UUID) -> Decimal:
    """
    Compute current balance: initial_balance + SUM(income) - SUM(expense).
    Query pushed to PostgreSQL per DATABASE.md §3.4.
    """
    result = await db.execute(
        select(
            Account.initial_balance,
            func.coalesce(
                func.sum(
                    case(
                        (Transaction.type == "income", Transaction.total_amount),
                        else_=-Transaction.total_amount,
                    )
                ),
                Decimal("0"),
            ).label("delta"),
        )
        .join(Transaction, Transaction.account_id == Account.id, isouter=True)
        .where(Account.id == account_id)
        .group_by(Account.id, Account.initial_balance)
    )
    row = result.first()
    if not row:
        return Decimal("0")
    return Decimal(str(row.initial_balance)) + Decimal(str(row.delta))


async def list_accounts(db: AsyncSession, user_id: uuid.UUID) -> list[dict]:
    """Return all accounts for user with computed balance."""
    result = await db.execute(
        select(Account).where(Account.user_id == user_id).order_by(Account.created_at.asc())
    )
    accounts = result.scalars().all()

    out = []
    for acc in accounts:
        balance = await _computed_balance(db, acc.id)
        out.append({**acc.__dict__, "current_balance": balance})
    return out


async def get_account(db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID) -> dict:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    acc = result.scalar_one_or_none()
    if not acc:
        raise ValueError("Akun tidak ditemukan.")
    balance = await _computed_balance(db, acc.id)
    return {**acc.__dict__, "current_balance": balance}


async def create_account(
    db: AsyncSession, user_id: uuid.UUID, payload: AccountCreateRequest, source: str
) -> dict:
    acc = Account(
        user_id=user_id,
        account_name=payload.account_name,
        bank_name=payload.bank_name,
        initial_balance=payload.initial_balance,
    )
    db.add(acc)
    await db.flush()

    await log_action(
        db,
        user_id=user_id,
        action="create",
        entity_type="account",
        entity_id=acc.id,
        new_value={"account_name": acc.account_name, "initial_balance": str(acc.initial_balance)},
        source=source,
    )

    logger.info("account_created", user_id=str(user_id), account_id=str(acc.id))
    return {**acc.__dict__, "current_balance": acc.initial_balance}


async def update_account(
    db: AsyncSession, user_id: uuid.UUID, account_id: uuid.UUID, payload: AccountUpdateRequest, source: str
) -> dict:
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id)
    )
    acc = result.scalar_one_or_none()
    if not acc:
        raise ValueError("Akun tidak ditemukan.")

    old_snap = {"account_name": acc.account_name, "bank_name": acc.bank_name}

    if payload.account_name is not None:
        acc.account_name = payload.account_name
    if payload.bank_name is not None:
        acc.bank_name = payload.bank_name
    acc.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        user_id=user_id,
        action="update",
        entity_type="account",
        entity_id=acc.id,
        old_value=old_snap,
        new_value={"account_name": acc.account_name, "bank_name": acc.bank_name},
        source=source,
    )

    balance = await _computed_balance(db, acc.id)
    return {**acc.__dict__, "current_balance": balance}


async def deactivate_account(
    db: AsyncSession,
    user_id: uuid.UUID,
    account_id: uuid.UUID,
    payload: AccountDeactivateRequest,
    source: str,
) -> None:
    """
    Deactivate an account per US-22:
    - If remaining balance != 0, target_account_id required.
    - Creates balancing transactions (does NOT mutate historical data).
    - Sets is_active = FALSE.
    """
    result = await db.execute(
        select(Account).where(Account.id == account_id, Account.user_id == user_id, Account.is_active == True)
    )
    acc = result.scalar_one_or_none()
    if not acc:
        raise ValueError("Akun aktif tidak ditemukan.")

    balance = await _computed_balance(db, account_id)

    if balance != Decimal("0"):
        if not payload.target_account_id:
            raise ValueError(
                f"Akun masih memiliki saldo Rp{balance:,.0f}. Pilih akun tujuan untuk memindahkan saldo."
            )

        # Verify target account exists and belongs to user
        target_result = await db.execute(
            select(Account).where(
                Account.id == payload.target_account_id,
                Account.user_id == user_id,
                Account.is_active == True,
            )
        )
        target_acc = target_result.scalar_one_or_none()
        if not target_acc:
            raise ValueError("Akun tujuan tidak ditemukan atau tidak aktif.")

        # Get system transfer category
        cat_result = await db.execute(
            select(Category).where(
                Category.user_id == None,
                Category.name == "Transfer/Penyesuaian Akun",
                Category.is_default == True,
            )
        )
        cats = cat_result.scalars().all()
        income_cat = next((c for c in cats if c.type == "income"), None)
        expense_cat = next((c for c in cats if c.type == "expense"), None)
        if not income_cat or not expense_cat:
            raise RuntimeError("Kategori system Transfer/Penyesuaian Akun tidak ditemukan. Jalankan migration seed.")

        now = datetime.now(timezone.utc)
        abs_balance = abs(balance)
        tx_type_source = "expense" if balance > 0 else "income"
        tx_type_target = "income" if balance > 0 else "expense"
        cat_source = expense_cat if tx_type_source == "expense" else income_cat
        cat_target = income_cat if tx_type_target == "income" else expense_cat

        # Balancing transaction on source account
        tx_out = Transaction(
            user_id=user_id,
            type=tx_type_source,
            total_amount=abs_balance,
            category_id=cat_source.id,
            account_id=account_id,
            source=source,
            note=f"Penyesuaian saldo — nonaktifkan akun ke {target_acc.account_name}",
            transaction_date=now,
        )
        # Balancing transaction on target account
        tx_in = Transaction(
            user_id=user_id,
            type=tx_type_target,
            total_amount=abs_balance,
            category_id=cat_target.id,
            account_id=payload.target_account_id,
            source=source,
            note=f"Penyesuaian saldo — dari akun {acc.account_name}",
            transaction_date=now,
        )
        db.add_all([tx_out, tx_in])
        await db.flush()

    acc.is_active = False
    acc.updated_at = datetime.now(timezone.utc)

    await log_action(
        db,
        user_id=user_id,
        action="update",
        entity_type="account",
        entity_id=acc.id,
        old_value={"is_active": True},
        new_value={"is_active": False, "remaining_balance": str(balance)},
        source=source,
    )
    logger.info("account_deactivated", user_id=str(user_id), account_id=str(account_id), balance=str(balance))
