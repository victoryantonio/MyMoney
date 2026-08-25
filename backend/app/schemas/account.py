"""
Pydantic v2 schemas for accounts.

Balance is computed at query time (initial_balance + SUM of transactions),
not stored — so it appears only in response schemas, never in DB models.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field, Field


class AccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


class AccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=100)
    bank_name: str | None = None


class AccountDeactivateRequest(BaseModel):
    """
    Body for deactivating an account (ARCHITECTURE.md §4.4, CODING_RULES §2.8).

    target_account_id is REQUIRED when the source account has a non-zero
    balance — the leftover funds must be transferred to another active account
    via balancing transactions. Accounts are NEVER deleted; history is kept.
    """

    target_account_id: uuid.UUID | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    account_name: str
    bank_name: str | None
    initial_balance: Decimal
    current_balance: Decimal  # computed field, not in DB
    net_balance: Decimal = Field(default=Decimal("0.00"))  # income − expense for this account
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
