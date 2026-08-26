"""pending_transactions

Creates the pending_transactions table — LLM parse results awaiting user
confirmation before becoming real transactions (CODING_RULES §2.4,
REQUIREMENTS US-05/US-08).

Revision ID: 0002
Revises: 0001
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import JSONB, UUID

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_transactions",
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
        sa.Column("merchant", sa.String(150), nullable=True),
        sa.Column("source", sa.String(10), nullable=False),
        sa.Column("note", sa.Text, nullable=True),
        sa.Column("confidence", sa.String(10), nullable=True),
        sa.Column("raw_input", sa.Text, nullable=True),
        sa.Column("items", JSONB, nullable=True),
        sa.Column(
            "created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()
        ),
        sa.Column("expires_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("type IN ('income', 'expense')", name="pending_transactions_type_check"),
        sa.CheckConstraint("total_amount > 0", name="pending_transactions_amount_positive"),
        sa.CheckConstraint(
            "source IN ('telegram', 'app')", name="pending_transactions_source_check"
        ),
    )
    op.create_index("idx_pending_transactions_user_id", "pending_transactions", ["user_id"])
    op.create_index(
        "idx_pending_transactions_user_created",
        "pending_transactions",
        ["user_id", sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("idx_pending_transactions_user_created", table_name="pending_transactions")
    op.drop_index("idx_pending_transactions_user_id", table_name="pending_transactions")
    op.drop_table("pending_transactions")
