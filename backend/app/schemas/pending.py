"""
Pydantic v2 schemas untuk `pending_transactions`.

Pending adalah baris setengah jadi: hasil parse (mis. baris mutasi bank yang
belum cocok dengan transaksi tercatat) BELUM menjadi transaksi nyata sampai
user menekan "Konfirmasi" (CODING_RULES §2.4). Skema ini dipakai layar
"Matching" di app Flutter untuk menampilkan, mengonfirmasi, dan membatalkan
pending.
"""

import uuid
from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class PendingTransactionResponse(BaseModel):
    """
    Satu baris pending beserta nama kategori/akun yang sudah di-resolve.

    `category_name`/`account_name` diisi server agar app tidak perlu memanggil
    endpoint kategori/akun lagi hanya untuk menampilkan label.
    """

    id: uuid.UUID
    action: str
    type: str
    total_amount: Decimal
    category_id: uuid.UUID
    category_name: str | None = None
    account_id: uuid.UUID | None = None
    account_name: str | None = None
    merchant: str | None = None
    note: str | None = None
    source: str
    confidence: str | None = None
    raw_input: str | None = None
    target_transaction_id: uuid.UUID | None = None
    created_at: datetime
    expires_at: datetime
    transaction_date: datetime | None = None
    timezone: str | None = None


class PendingListResponse(BaseModel):
    """Daftar pending aktif + jumlah totalnya (untuk badge tombol)."""

    items: list[PendingTransactionResponse]
    total: int


class PendingConfirmResponse(BaseModel):
    """Hasil konfirmasi: id transaksi nyata yang baru dibuat/diubah."""

    pending_id: uuid.UUID
    transaction_id: uuid.UUID
    action: str
    type: str
    total_amount: Decimal


class PendingCancelResponse(BaseModel):
    """Hasil pembatalan: id pending yang sudah dibuang."""

    pending_id: uuid.UUID
    cancelled: bool = True


class PendingCountResponse(BaseModel):
    """Jumlah pending aktif — dipakai badge tombol "Matching"."""

    count: int = Field(ge=0)
