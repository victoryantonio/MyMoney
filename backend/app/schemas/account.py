"""
Pydantic v2 schemas for accounts.

Balance is computed at query time (initial_balance + SUM of transactions),
not stored — so it appears only in response schemas, never in DB models.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class AccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    initial_balance: Decimal = Field(default=Decimal("0.00"), ge=0)


class AccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=100)
    bank_name: str | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    account_name: str
    bank_name: str | None
    initial_balance: Decimal
    current_balance: Decimal  # computed field, not in DB
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}
