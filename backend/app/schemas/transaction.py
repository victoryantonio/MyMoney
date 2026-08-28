"""
Pydantic v2 schemas for transactions and transaction items.

Cursor-based pagination uses `cursor` (the last seen transaction's created_at ISO string)
so it stays stable even as new transactions are inserted — page-based pagination
breaks on inserts, which would be frequent here.
"""

import uuid
from datetime import datetime
from decimal import Decimal
from typing import Literal

from pydantic import BaseModel, Field

# ── Item sub-schemas ─────────────────────────────────────────────────────────


class TransactionItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)


class TransactionItemResponse(BaseModel):
    id: uuid.UUID
    name: str
    qty: Decimal
    price: Decimal

    model_config = {"from_attributes": True}


# ── Transaction request schemas ───────────────────────────────────────────────


class TransactionCreateRequest(BaseModel):
    type: Literal["income", "expense", "transfer"]
    total_amount: Decimal = Field(gt=0)
    # Wajib untuk income/expense; NULL untuk transfer.
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID
    # Akun tujuan — hanya untuk type == 'transfer'.
    to_account_id: uuid.UUID | None = None
    merchant: str | None = Field(default=None, max_length=150)
    note: str | None = None
    transaction_date: datetime
    items: list[TransactionItemCreate] = Field(default_factory=list)


class TransactionUpdateRequest(BaseModel):
    """All fields optional — PATCH semantics."""

    type: Literal["income", "expense", "transfer"] | None = None
    total_amount: Decimal | None = Field(default=None, gt=0)
    category_id: uuid.UUID | None = None
    account_id: uuid.UUID | None = None
    to_account_id: uuid.UUID | None = None
    merchant: str | None = None
    note: str | None = None
    transaction_date: datetime | None = None
    items: list[TransactionItemCreate] | None = None


# ── Transaction response schemas ──────────────────────────────────────────────


class TransactionResponse(BaseModel):
    id: uuid.UUID
    type: str
    total_amount: Decimal
    category_id: uuid.UUID | None  # NULL untuk transfer
    account_id: uuid.UUID
    to_account_id: uuid.UUID | None  # hanya terisi saat transfer
    merchant: str | None
    source: str
    note: str | None
    confidence: str | None
    receipt_image_url: str | None
    transaction_date: datetime
    created_at: datetime
    updated_at: datetime
    items: list[TransactionItemResponse] = []

    model_config = {"from_attributes": True}


# ── Pagination wrapper ────────────────────────────────────────────────────────


class TransactionListResponse(BaseModel):
    """
    Cursor-based pagination response.

    `next_cursor` is the ISO-formatted created_at of the last item in this page.
    Pass it as `?cursor=<value>` on the next request to get the next page.
    None means this is the last page.
    """

    items: list[TransactionResponse]
    next_cursor: str | None
    total_count: int
