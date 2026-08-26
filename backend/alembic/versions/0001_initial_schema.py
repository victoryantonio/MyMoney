"""initial_schema

Creates all tables for MyMoney v1:
  users, telegram_links, categories, accounts,
  transactions, transaction_items, audit_logs

Also seeds global default categories.

Revision ID: 0001
Revises:
Create Date: 2026-08-23
"""

import uuid

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── users ─────────────────────────────────────────────────────────────────
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Jakarta"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # ── telegram_links ─────────────────────────────────────────────────────────
    op.create_table(
        "telegram_links",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
            unique=True,
        ),
        sa.Column("telegram_id", sa.BigInteger, nullable=False),
        sa.Column(
            "linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index(
        "idx_telegram_links_telegram_id", "telegram_links", ["telegram_id"], unique=True
    )

    # ── categories ────────────────────────────────────────────────────────────
    op.create_table(
        "categories",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("is_default", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("type IN ('income', 'expense')", name="categories_type_check"),
    )
    op.create_index("idx_categories_user_id", "categories", ["user_id"])

    # ── accounts ──────────────────────────────────────────────────────────────
    op.create_table(
        "accounts",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("initial_balance", sa.Numeric(14, 2), nullable=False, server_default="0"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
    )
    op.create_index("idx_accounts_user_id", "accounts", ["user_id"])

    # ── transactions ──────────────────────────────────────────────────────────
    op.create_table(
        "transactions",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column(
            "category_id", UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("merchant", sa.String(150), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("receipt_image_url", sa.Text, nullable=True),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column(
            "updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint("type IN ('income', 'expense')", name="transactions_type_check"),
        sa.CheckConstraint("total_amount > 0", name="transactions_amount_positive"),
        sa.CheckConstraint("source IN ('telegram', 'app')", name="transactions_source_check"),
        sa.CheckConstraint(
            "confidence IN ('high', 'medium', 'low') OR confidence IS NULL",
            name="transactions_confidence_check",
        ),
    )
    # Composite index — covers almost all list & report queries per DATABASE.md §3.1
    op.create_index(
        "idx_transactions_user_date", "transactions", ["user_id", sa.text("transaction_date DESC")]
    )
    op.create_index("idx_transactions_user_category", "transactions", ["user_id", "category_id"])
    op.create_index("idx_transactions_category_id", "transactions", ["category_id"])
    op.create_index("idx_transactions_account_id", "transactions", ["account_id"])

    # ── transaction_items ─────────────────────────────────────────────────────
    op.create_table(
        "transaction_items",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("qty", sa.Numeric(10, 2), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="transaction_items_qty_positive"),
        sa.CheckConstraint("price >= 0", name="transaction_items_price_non_negative"),
    )
    op.create_index("idx_transaction_items_transaction_id", "transaction_items", ["transaction_id"])

    # ── audit_logs ────────────────────────────────────────────────────────────
    op.create_table(
        "audit_logs",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", JSONB, nullable=True),
        sa.Column("new_value", JSONB, nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.CheckConstraint(
            "action IN ('create', 'update', 'delete', 'login', 'login_failed')",
            name="audit_logs_action_check",
        ),
        sa.CheckConstraint("source IN ('telegram', 'app')", name="audit_logs_source_check"),
    )
    op.create_index(
        "idx_audit_logs_user_created", "audit_logs", ["user_id", sa.text("created_at DESC")]
    )

    # ── Seed: global default categories (user_id = NULL) ─────────────────────
    categories_table = sa.table(
        "categories",
        sa.column("id", UUID(as_uuid=True)),
        sa.column("user_id", UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("is_active", sa.Boolean),
    )
    op.bulk_insert(
        categories_table,
        [
            # Expense
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000001"),
                "user_id": None,
                "name": "Food",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000002"),
                "user_id": None,
                "name": "Transport",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000003"),
                "user_id": None,
                "name": "Shopping",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000004"),
                "user_id": None,
                "name": "Bills",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000005"),
                "user_id": None,
                "name": "Entertainment",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000006"),
                "user_id": None,
                "name": "Health",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000007"),
                "user_id": None,
                "name": "Education",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000008"),
                "user_id": None,
                "name": "Other",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            # Transfer/Adjustment (for account deactivation balancing)
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000009"),
                "user_id": None,
                "name": "Transfer",
                "type": "expense",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000010"),
                "user_id": None,
                "name": "Transfer",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
            # Income
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000011"),
                "user_id": None,
                "name": "Salary",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000012"),
                "user_id": None,
                "name": "Bonus",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000013"),
                "user_id": None,
                "name": "Investment",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000014"),
                "user_id": None,
                "name": "Gift",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
            {
                "id": uuid.UUID("10000000-0000-0000-0000-000000000015"),
                "user_id": None,
                "name": "Other",
                "type": "income",
                "is_default": True,
                "is_active": True,
            },
        ],
    )


def downgrade() -> None:
    op.drop_table("audit_logs")
    op.drop_table("transaction_items")
    op.drop_table("transactions")
    op.drop_table("accounts")
    op.drop_table("categories")
    op.drop_table("telegram_links")
    op.drop_table("users")
