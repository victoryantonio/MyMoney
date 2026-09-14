"""processed_updates

Telegram webhook idempotency: one row per update_id so retries / duplicate
deliveries do not re-run parse/write.

Revision ID: 0010
Revises: 0009
Create Date: 2026-09-12
"""

import sqlalchemy as sa

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "processed_updates",
        sa.Column("update_id", sa.BigInteger, primary_key=True),
        sa.Column(
            "received_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column("status", sa.Text, nullable=False, server_default="received"),
        sa.Column("processed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("error", sa.Text, nullable=True),
        sa.CheckConstraint(
            "status IN ('received', 'processing', 'done', 'failed')",
            name="processed_updates_status_check",
        ),
    )


def downgrade() -> None:
    op.drop_table("processed_updates")
