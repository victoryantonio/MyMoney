"""
Pending transaction — LLM parse results awaiting user confirmation.

CODING_RULES §2.4: "Tidak ada hasil parsing LLM yang langsung commit ke
database tanpa melalui state pending confirmation" (REQUIREMENTS US-05/US-08).

Flow:
  LLM parse → PendingTransaction (NOT a real transaction)
  → user confirms → Transaction created + pending row deleted
  → user cancels → pending row deleted, nothing persisted.

`raw_input` stores the original user text (and later, image metadata) for
prompt-injection forensics (CODING_RULES §2.9.B.4).
"""

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
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class PendingTransaction(Base):
    __tablename__ = "pending_transactions"
    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="pending_transactions_type_check"),
        CheckConstraint("total_amount > 0", name="pending_transactions_amount_positive"),
        CheckConstraint("source IN ('telegram', 'app')", name="pending_transactions_source_check"),
        CheckConstraint("action IN ('create', 'update')", name="pending_transactions_action_check"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    action: Mapped[str] = mapped_column(String(10), nullable=False, default="create")
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    raw_input: Mapped[str | None] = mapped_column(Text, nullable=True)
    items: Mapped[list | None] = mapped_column(JSONB, nullable=True)
    target_transaction_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    user: Mapped["Profile"] = relationship(back_populates="pending_transactions")  # noqa: F821
    category: Mapped["Category"] = relationship(back_populates="pending_transactions")  # noqa: F821
