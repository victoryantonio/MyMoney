import uuid
from datetime import datetime

from sqlalchemy import Boolean, DateTime, String, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, default="Asia/Jakarta")
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
    telegram_link: Mapped["TelegramLink"] = relationship(  # noqa: F821
        back_populates="user", uselist=False
    )
    categories: Mapped[list["Category"]] = relationship(back_populates="user")  # noqa: F821
    accounts: Mapped[list["Account"]] = relationship(back_populates="user")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")  # noqa: F821
    pending_transactions: Mapped[list["PendingTransaction"]] = relationship(  # noqa: F821
        back_populates="user"
    )
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")  # noqa: F821
