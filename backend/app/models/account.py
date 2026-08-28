import uuid
from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, CheckConstraint, DateTime, ForeignKey, Numeric, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class Account(Base):
    __tablename__ = "accounts"
    __table_args__ = (
        CheckConstraint(
            "account_type IN ('cash', 'ewallet', 'bank')",
            name="accounts_type_check",
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    # Jenis akun: 'cash' | 'ewallet' | 'bank' (migrasi 0008 — pengganti bank_name)
    account_type: Mapped[str] = mapped_column(String(10), nullable=False, default="cash")
    # Seed balance at account creation; current balance is computed (not stored)
    initial_balance: Mapped[Decimal] = mapped_column(
        Numeric(14, 2), nullable=False, default=Decimal("0.00")
    )
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
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
    user: Mapped["Profile"] = relationship(back_populates="accounts")  # noqa: F821
    # foreign_keys wajib — Transaction punya 2 FK ke accounts (account_id + to_account_id).
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="account",
        foreign_keys="Transaction.account_id",
    )
