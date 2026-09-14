"""Per-user merchant alias learned from corrections."""

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class MerchantAlias(Base):
    __tablename__ = "merchant_aliases"
    __table_args__ = (
        UniqueConstraint("user_id", "merchant_key", name="uq_merchant_aliases_user_key"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=False
    )
    merchant_key: Mapped[str] = mapped_column(String(150), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False
    )
    account_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="SET NULL"), nullable=True
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    last_corrected_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    user: Mapped["Profile"] = relationship()  # noqa: F821
    category: Mapped["Category"] = relationship()  # noqa: F821
    account: Mapped["Account | None"] = relationship()  # noqa: F821
