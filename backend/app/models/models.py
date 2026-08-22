import uuid
from datetime import datetime, timezone

from sqlalchemy import Boolean, CheckConstraint, ForeignKey, Numeric, String, Text
from sqlalchemy import BigInteger, DateTime, Integer
from sqlalchemy.dialects.postgresql import UUID, JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy.sql import func


class Base(DeclarativeBase):
    pass


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# users
# ---------------------------------------------------------------------------
class User(Base):
    __tablename__ = "users"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(100), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    # relationships
    telegram_link: Mapped["TelegramLink"] = relationship("TelegramLink", back_populates="user", uselist=False)
    categories: Mapped[list["Category"]] = relationship("Category", back_populates="user")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="user")
    accounts: Mapped[list["Account"]] = relationship("Account", back_populates="user")
    audit_logs: Mapped[list["AuditLog"]] = relationship("AuditLog", back_populates="user")


# ---------------------------------------------------------------------------
# telegram_links
# ---------------------------------------------------------------------------
class TelegramLink(Base):
    __tablename__ = "telegram_links"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, unique=True)
    telegram_id: Mapped[int] = mapped_column(BigInteger, unique=True, nullable=False, index=True)
    linked_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="telegram_link")


# ---------------------------------------------------------------------------
# categories
# ---------------------------------------------------------------------------
class Category(Base):
    __tablename__ = "categories"
    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_categories_type"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(50), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    user: Mapped["User | None"] = relationship("User", back_populates="categories")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="category")


# ---------------------------------------------------------------------------
# accounts
# ---------------------------------------------------------------------------
class Account(Base):
    __tablename__ = "accounts"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False, index=True)
    account_name: Mapped[str] = mapped_column(String(100), nullable=False)
    bank_name: Mapped[str | None] = mapped_column(String(100), nullable=True)
    initial_balance: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False, default=0)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="accounts")
    transactions: Mapped[list["Transaction"]] = relationship("Transaction", back_populates="account")


# ---------------------------------------------------------------------------
# transactions
# ---------------------------------------------------------------------------
class Transaction(Base):
    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("type IN ('income', 'expense')", name="ck_transactions_type"),
        CheckConstraint("total_amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint("source IN ('telegram', 'app')", name="ck_transactions_source"),
        CheckConstraint("confidence IN ('high', 'medium', 'low')", name="ck_transactions_confidence"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type: Mapped[str] = mapped_column(String(10), nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)
    category_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("categories.id"), nullable=False)
    account_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("accounts.id", ondelete="RESTRICT"), nullable=False
    )
    merchant: Mapped[str | None] = mapped_column(String(150), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    receipt_image_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
    confidence: Mapped[str | None] = mapped_column(String(10), nullable=True)
    transaction_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow, onupdate=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="transactions")
    category: Mapped["Category"] = relationship("Category", back_populates="transactions")
    account: Mapped["Account"] = relationship("Account", back_populates="transactions")
    items: Mapped[list["TransactionItem"]] = relationship(
        "TransactionItem", back_populates="transaction", cascade="all, delete-orphan"
    )


# ---------------------------------------------------------------------------
# transaction_items
# ---------------------------------------------------------------------------
class TransactionItem(Base):
    __tablename__ = "transaction_items"
    __table_args__ = (
        CheckConstraint("qty > 0", name="ck_transaction_items_qty_positive"),
        CheckConstraint("price >= 0", name="ck_transaction_items_price_nonneg"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("transactions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(150), nullable=False)
    qty: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    price: Mapped[float] = mapped_column(Numeric(14, 2), nullable=False)

    transaction: Mapped["Transaction"] = relationship("Transaction", back_populates="items")


# ---------------------------------------------------------------------------
# audit_logs
# ---------------------------------------------------------------------------
class AuditLog(Base):
    __tablename__ = "audit_logs"
    __table_args__ = (
        CheckConstraint("action IN ('create', 'update', 'delete', 'login')", name="ck_audit_logs_action"),
        CheckConstraint("source IN ('telegram', 'app')", name="ck_audit_logs_source"),
    )

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    action: Mapped[str] = mapped_column(String(20), nullable=False)
    entity_type: Mapped[str] = mapped_column(String(30), nullable=False)
    entity_id: Mapped[uuid.UUID | None] = mapped_column(UUID(as_uuid=True), nullable=True)
    old_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    new_value: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
    ip_address: Mapped[str | None] = mapped_column(String(45), nullable=True)
    source: Mapped[str] = mapped_column(String(10), nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, default=utcnow)

    user: Mapped["User"] = relationship("User", back_populates="audit_logs")
