"""pending_edit_support

Adds `action` ('create'|'update') and `target_transaction_id` to
pending_transactions so that LLM-driven *edits* (e.g. Telegram /edit) can also
go through the pending-confirmation gate (CODING_RULES §2.4, REQUIREMENTS
US-05/US-08) instead of committing parsed output directly.

Revision ID: 0003
Revises: 0002
Create Date: 2026-08-24
"""

import sqlalchemy as sa
from alembic import op
from sqlalchemy.dialects.postgresql import UUID

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_transactions",
        sa.Column(
            "action",
            sa.String(10),
            nullable=False,
            server_default="create",
        ),
    )
    op.add_column(
        "pending_transactions",
        sa.Column(
            "target_transaction_id",
            UUID(as_uuid=True),
            sa.ForeignKey("transactions.id", ondelete="CASCADE"),
            nullable=True,
        ),
    )
    op.create_check_constraint(
        "pending_transactions_action_check",
        "pending_transactions",
        "action IN ('create', 'update')",
    )
    op.create_index(
        "idx_pending_transactions_action",
        "pending_transactions",
        ["action"],
    )


def downgrade() -> None:
    op.drop_index("idx_pending_transactions_action", table_name="pending_transactions")
    op.drop_constraint(
        "pending_transactions_action_check", "pending_transactions", type_="check"
    )
    op.drop_column("pending_transactions", "target_transaction_id")
    op.drop_column("pending_transactions", "action")
