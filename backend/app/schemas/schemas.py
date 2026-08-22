import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator


# ---------------------------------------------------------------------------
# Auth schemas
# ---------------------------------------------------------------------------
class UserRegisterRequest(BaseModel):
    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    display_name: str = Field(min_length=1, max_length=100)


class UserLoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"


class RefreshTokenRequest(BaseModel):
    refresh_token: str


class UserResponse(BaseModel):
    id: uuid.UUID
    email: str
    display_name: str
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Category schemas
# ---------------------------------------------------------------------------
class CategoryResponse(BaseModel):
    id: uuid.UUID
    name: str
    type: Literal["income", "expense"]
    is_default: bool
    user_id: uuid.UUID | None

    model_config = {"from_attributes": True}


class CategoryCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    type: Literal["income", "expense"]


class CategoryUpdateRequest(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=50)


# ---------------------------------------------------------------------------
# Account schemas
# ---------------------------------------------------------------------------
class AccountCreateRequest(BaseModel):
    account_name: str = Field(min_length=1, max_length=100)
    bank_name: str | None = Field(default=None, max_length=100)
    initial_balance: Decimal = Field(default=Decimal("0"), ge=0)


class AccountUpdateRequest(BaseModel):
    account_name: str | None = Field(default=None, min_length=1, max_length=100)
    bank_name: str | None = None


class AccountDeactivateRequest(BaseModel):
    """When deactivating an account with remaining balance, target account is required."""
    target_account_id: uuid.UUID | None = None


class AccountResponse(BaseModel):
    id: uuid.UUID
    account_name: str
    bank_name: str | None
    initial_balance: Decimal
    current_balance: Decimal  # computed field, not stored
    is_active: bool
    created_at: datetime

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Transaction schemas
# ---------------------------------------------------------------------------
class TransactionItemRequest(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)


class TransactionItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    qty: Decimal
    price: Decimal

    model_config = {"from_attributes": True}


class TransactionCreateRequest(BaseModel):
    type: Literal["income", "expense"]
    total_amount: Decimal = Field(gt=0)
    category_id: uuid.UUID
    account_id: uuid.UUID
    merchant: str | None = Field(default=None, max_length=150)
    note: str | None = None
    transaction_date: datetime
    items: list[TransactionItemRequest] = Field(default_factory=list)

    @field_validator("total_amount")
    @classmethod
    def amount_must_be_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("total_amount must be greater than 0")
        return v


class TransactionUpdateRequest(BaseModel):
    type: Literal["income", "expense"] | None = None
    total_amount: Decimal | None = Field(default=None, gt=0)
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    merchant: str | None = None
    note: str | None = None
    transaction_date: datetime | None = None
    items: list[TransactionItemRequest] | None = None


class TransactionResponse(BaseModel):
    id: uuid.UUID
    type: Literal["income", "expense"]
    total_amount: Decimal
    category_id: uuid.UUID
    category: CategoryResponse
    account_id: uuid.UUID
    merchant: str | None
    source: str
    note: str | None
    confidence: str | None
    receipt_image_url: str | None
    transaction_date: datetime
    created_at: datetime
    updated_at: datetime
    items: list[TransactionItemResponse]

    model_config = {"from_attributes": True}


# ---------------------------------------------------------------------------
# Pagination
# ---------------------------------------------------------------------------
class CursorPage(BaseModel):
    """Cursor-based pagination response wrapper per DATABASE.md §3.2."""
    data: list
    next_cursor: str | None  # opaque cursor — encodes (transaction_date, id)
    has_more: bool
