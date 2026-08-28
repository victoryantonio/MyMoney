import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Numeric,
    String,
    Text,
    func,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint(
            "type IN ('income', 'expense', 'transfer')",
            name="transactions_type_check",
        ),
        CheckConstraint("total_amount > 0", name="transactions_amount_positive"),
        CheckConstraint("source IN ('telegram', 'app')", name="transactions_source_check"),
        CheckConstraint(
            "confidence IN ('high', 'medium', 'low') OR confidence IS NULL",
            name="transactions_confidence_check",
        ),
        CheckConstraint(
            "char_length(original_currency) = 3",
            name="transactions_currency_length",
        ),
        CheckConstraint(
            "exchange_rate > 0",
            name="transactions_exchange_rate_positive",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    # Use NUMERIC, not FLOAT — mandatory for financial values to avoid floating-point errors
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    # Mata uang asli saat input (ISO 4217); total_amount SELALU dalam IDR.
    # exchange_rate = 1 unit original_currency berapa IDR (default 1 → IDR).
    original_currency: Mapped[str] = mapped_column(
        String(3), nullable=False, server_default="IDR", default="IDR"
    )
    exchange_rate: Mapped[Decimal] = mapped_column(
        Numeric(18, 6), nullable=False, server_default="1", default=Decimal("1")
    )
    # NULL untuk transaksi transfer — transfer tidak memakai kategori
    category_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=True
    )
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("accounts.id", ondelete="RESTRICT"),
        nullable=False,
    )
    # Akun tujuan transfer (hanya terisi saat type == 'transfer')
    to_account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id"), nullable=True
    )
    merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    receipt_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    # Only populated when the transaction originates from LLM parsing
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    # Actual transaction date (may differ from created_at if user back-dates)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships
    user: Mapped["Profile"] = relationship(back_populates="transactions")  # noqa: F821
    category: Mapped["Category"] = relationship(back_populates="transactions")  # noqa: F821
    # foreign_keys wajib — ada 2 FK ke accounts (account_id + to_account_id).
    account: Mapped["Account"] = relationship(  # noqa: F821
        back_populates="transactions",
        foreign_keys="Transaction.account_id",
    )
    items: Mapped[list["TransactionItem"]] = relationship(  # noqa: F821
        back_populates="transaction",
        cascade="all, delete-orphan",
    )
