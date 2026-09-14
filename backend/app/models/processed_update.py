from datetime import datetime

from sqlalchemy import BigInteger, CheckConstraint, DateTime, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class ProcessedUpdate(Base):
    """Idempotency record for a Telegram update_id (no full payload)."""

    __tablename__ = "processed_updates"
    __table_args__ = (
        CheckConstraint(
            "status IN ('received', 'processing', 'done', 'failed')",
            name="processed_updates_status_check",
        ),
    )

    update_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    received_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    status: Mapped[str] = mapped_column(Text, nullable=False, server_default="received")
    processed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    error: Mapped[str | None] = mapped_column(Text, nullable=True)
