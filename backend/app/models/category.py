import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    String,
    and_,
    exists,
    func,
    or_,
    select,
    text,
)
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, aliased, mapped_column, relationship

from app.db.base import Base

# Sentinel for global categories (user_id IS NULL) — DATABASE.md §2.3.
_GLOBAL_OWNER_UUID = "00000000-0000-0000-0000-000000000000"


def category_visible_clause(user_id: uuid.UUID):
    """
    WHERE filter: kategori yang terlihat oleh user.

    Terlihat = aktif DAN (milik user ATAU default global yang tidak
    disembunyikan oleh baris "shadow" non-aktif milik user — dipakai saat
    user menghapus kategori default global hanya untuk dirinya sendiri).
    """
    shadow = aliased(Category)
    hidden = exists(
        select(shadow.id).where(
            shadow.user_id == user_id,
            shadow.is_active.is_(False),
            shadow.name == Category.name,
            shadow.type == Category.type,
        )
    )
    return and_(
        Category.is_active.is_(True),
        or_(
            Category.user_id == user_id,
            and_(Category.user_id.is_(None), ~hidden),
        ),
    )


class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        # 'transfer' disertakan sejak migrasi 0008 (tipe transaksi transfer,
        # walau transaksi transfer TIDAK memakai kategori).
        CheckConstraint("type IN ('income', 'expense', 'transfer')", name="categories_type_check"),
        # Partial (WHERE is_active = TRUE) — migrasi 0008 — supaya baris shadow
        # per-user (is_active=FALSE) tidak bentrok dengan kategori custom baru.
        # lower(name) — migrasi 0009 — nama unik per user bersifat
        # case-insensitive ('Kuliner' vs 'kuliner' tidak boleh sama).
        Index(
            "idx_categories_user_name_type",
            func.coalesce("user_id", _GLOBAL_OWNER_UUID),
            func.lower("name"),
            "type",
            unique=True,
            postgresql_where=text("is_active = TRUE"),
        ),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    # NULL = global default category (belongs to all users)
    user_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True), ForeignKey("profiles.id", ondelete="CASCADE"), nullable=True
    )
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    # Soft-delete: prevent FK breakage when user deletes a custom category
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )

    # Relationships
    user: Mapped["Profile | None"] = relationship(back_populates="categories")  # noqa: F821
    transactions: Mapped[list["Transaction"]] = relationship(  # noqa: F821
        back_populates="category"
    )
    pending_transactions: Mapped[list["PendingTransaction"]] = relationship(  # noqa: F821
        back_populates="category"
    )
