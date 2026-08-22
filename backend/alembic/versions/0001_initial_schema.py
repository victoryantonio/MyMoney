"""initial schema: all tables, indexes, and seed categories

Revision ID: 0001
Revises:
Create Date: 2026-08-22

"""
import uuid
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

revision: str = "0001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------ users
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # --------------------------------------------------------- telegram_links
    op.create_table(
        "telegram_links",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False, unique=True),
        sa.Column("telegram_id", sa.BigInteger(), nullable=False, unique=True),
        sa.Column("linked_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_telegram_links_telegram_id", "telegram_links", ["telegram_id"], unique=True)

    # ------------------------------------------------------------ categories
    op.create_table(
        "categories",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("name", sa.String(50), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("is_default", sa.Boolean(), nullable=False, server_default=sa.text("FALSE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("type IN ('income', 'expense')", name="ck_categories_type"),
    )
    op.create_index("idx_categories_user_id", "categories", ["user_id"])
    # Unique: no duplicate name+type per user (NULL user_id = global defaults)
    op.execute(
        """
        CREATE UNIQUE INDEX idx_categories_user_name_type
        ON categories (COALESCE(user_id, '00000000-0000-0000-0000-000000000000'), name, type)
        """
    )

    # ------------------------------------------------------------- accounts
    op.create_table(
        "accounts",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("account_name", sa.String(100), nullable=False),
        sa.Column("bank_name", sa.String(100), nullable=True),
        sa.Column("initial_balance", sa.Numeric(14, 2), nullable=False, server_default=sa.text("0")),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("TRUE")),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
    )
    op.create_index("idx_accounts_user_id", "accounts", ["user_id"])

    # ---------------------------------------------------------- transactions
    op.create_table(
        "transactions",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("type", sa.String(10), nullable=False),
        sa.Column("total_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("category_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("categories.id"), nullable=False),
        sa.Column(
            "account_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="RESTRICT"),
            nullable=False,
        ),
        sa.Column("merchant", sa.String(150), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("receipt_image_url", sa.Text(), nullable=True),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("type IN ('income', 'expense')", name="ck_transactions_type"),
        sa.CheckConstraint("total_amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint("source IN ('telegram', 'app')", name="ck_transactions_source"),
        sa.CheckConstraint("confidence IN ('high', 'medium', 'low')", name="ck_transactions_confidence"),
    )
    # Critical composite indexes from DATABASE.md §2.4
    op.create_index("idx_transactions_user_date", "transactions", ["user_id", sa.text("transaction_date DESC")])
    op.create_index("idx_transactions_user_category", "transactions", ["user_id", "category_id"])
    op.create_index("idx_transactions_category_id", "transactions", ["category_id"])
    op.create_index("idx_transactions_account_id", "transactions", ["account_id"])

    # ------------------------------------------------------- transaction_items
    op.create_table(
        "transaction_items",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column(
            "transaction_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("qty", sa.Numeric(10, 2), nullable=False),
        sa.Column("price", sa.Numeric(14, 2), nullable=False),
        sa.CheckConstraint("qty > 0", name="ck_transaction_items_qty_positive"),
        sa.CheckConstraint("price >= 0", name="ck_transaction_items_price_nonneg"),
    )
    op.create_index("idx_transaction_items_transaction_id", "transaction_items", ["transaction_id"])

    # ------------------------------------------------------------ audit_logs
    op.create_table(
        "audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True, server_default=sa.text("gen_random_uuid()")),
        sa.Column("user_id", postgresql.UUID(as_uuid=True), sa.ForeignKey("users.id"), nullable=False),
        sa.Column("action", sa.String(20), nullable=False),
        sa.Column("entity_type", sa.String(30), nullable=False),
        sa.Column("entity_id", postgresql.UUID(as_uuid=True), nullable=True),
        sa.Column("old_value", postgresql.JSONB(), nullable=True),
        sa.Column("new_value", postgresql.JSONB(), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.text("now()")),
        sa.CheckConstraint("action IN ('create', 'update', 'delete', 'login')", name="ck_audit_logs_action"),
        sa.CheckConstraint("source IN ('telegram', 'app')", name="ck_audit_logs_source"),
    )
    op.create_index("idx_audit_logs_user_created", "audit_logs", ["user_id", sa.text("created_at DESC")])

    # -------------------------------------------------- Seed: default categories
    # user_id = NULL means global/default category (accessible to all users)
    categories_table = sa.table(
        "categories",
        sa.column("id", postgresql.UUID(as_uuid=True)),
        sa.column("user_id", postgresql.UUID(as_uuid=True)),
        sa.column("name", sa.String),
        sa.column("type", sa.String),
        sa.column("is_default", sa.Boolean),
        sa.column("created_at", sa.DateTime(timezone=True)),
    )

    default_categories = [
        # Expense categories
        {"name": "Makanan", "type": "expense"},
        {"name": "Transport", "type": "expense"},
        {"name": "Belanja", "type": "expense"},
        {"name": "Tagihan", "type": "expense"},
        {"name": "Hiburan", "type": "expense"},
        {"name": "Kesehatan", "type": "expense"},
        {"name": "Pendidikan", "type": "expense"},
        {"name": "Lainnya", "type": "expense"},
        # Income categories
        {"name": "Gaji", "type": "income"},
        {"name": "Bonus", "type": "income"},
        {"name": "Investasi", "type": "income"},
        {"name": "Hadiah", "type": "income"},
        {"name": "Lainnya", "type": "income"},
        # System category for account balance transfers (DATABASE.md §2.4)
        {"name": "Transfer/Penyesuaian Akun", "type": "expense"},
        {"name": "Transfer/Penyesuaian Akun", "type": "income"},
    ]

    op.bulk_insert(
        categories_table,
        [
            {
                "id": uuid.uuid4(),
                "user_id": None,
                "name": cat["name"],
                "type": cat["type"],
                "is_default": True,
                "created_at": sa.text("now()"),
            }
            for cat in default_categories
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
