"""
Pydantic v2 schemas for accounts.

Balance is computed at query time (initial_balance + SUM of transactions),
not stored — so it appears only in response schemas, never in DB models.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field


class AccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    account_type: Literal["cash", "ewallet", "bank"] = "cash"
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


class AccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=100)
    account_type: Literal["cash", "ewallet", "bank"] | None = None


class AccountDeactivateRequest(BaseModel):
    """
    Deactivation request (ARCHITECTURE.md §4.4).

    `target_account_id` is REQUIRED when the account still has a non-zero
    balance — the balance is moved to the target via balancing transactions.
    """

    target_account_id: uuid.UUID | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    account_name: str
    account_type: str
    initial_balance: Decimal
    current_balance: Decimal  # computed field, not in DB
    net_balance: Decimal = Field(default=Decimal("0.00"))  # income − expense for this account
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
