"""Profile — tabel user aplikasi v2 (1:1 dengan auth.users milik Supabase).

id sama dengan auth.users.id; row dibuat otomatis oleh trigger
`on_auth_user_created` (handle_new_user) saat user register via Supabase Auth
(migration 0005). Backend memakai service_role (bypass RLS) untuk lookup.
"""

import uuid
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    Table,
    func,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base

if TYPE_CHECKING:
    from app.models.account import Account
    from app.models.audit_log import AuditLog
    from app.models.category import Category
    from app.models.pending_transaction import PendingTransaction
    from app.models.telegram_link import TelegramLink
    from app.models.transaction import Transaction

# auth.users hidup di skema `auth` milik Supabase (di luar ORM app). Table
# ringan ini hanya agar metadata SQLAlchemy bisa me-resolve FK
# profiles.id → auth.users.id (mapper configuration). App tidak pernah
# membuat/drop table ini — DB riil sudah dikelola Supabase.
_auth_users_table = Table(
    "users",
    Base.metadata,
    Column("id", UUID(as_uuid=True), primary_key=True),
    schema="auth",
)


class Profile(Base):
    __tablename__ = "profiles"

    id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("auth.users.id", ondelete="CASCADE"), primary_key=True
    )
    display_name: Mapped[str] = mapped_column(String(100), nullable=False, default="User")
    timezone: Mapped[str] = mapped_column(String(50), nullable=False, server_default="Asia/Jakarta")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default=text("true"))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )

    # Relationships (nama sama dengan v1 User — back_populates tidak berubah)
    telegram_link: Mapped["TelegramLink | None"] = relationship(
        back_populates="user", uselist=False
    )
    categories: Mapped[list["Category"]] = relationship(back_populates="user")
    accounts: Mapped[list["Account"]] = relationship(back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship(back_populates="user")
    pending_transactions: Mapped[list["PendingTransaction"]] = relationship(back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship(back_populates="user")
