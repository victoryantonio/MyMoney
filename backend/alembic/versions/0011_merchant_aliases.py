"""merchant aliases + pending account_id

Revision ID: 0011
Revises: 0010
Create Date: 2026-09-14
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "merchant_aliases",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "user_id",
            UUID(as_uuid=True),
            sa.ForeignKey("profiles.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("merchant_key", sa.String(150), nullable=False),
        sa.Column(
            "category_id",
            UUID(as_uuid=True),
            sa.ForeignKey("categories.id"),
            nullable=False,
        ),
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("hits", sa.Integer(), nullable=False, server_default="1"),
        sa.Column(
            "last_corrected_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.UniqueConstraint("user_id", "merchant_key", name="uq_merchant_aliases_user_key"),
    )
    op.create_index("idx_merchant_aliases_user_id", "merchant_aliases", ["user_id"])

    op.add_column(
        "pending_transactions",
        sa.Column(
            "account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id", ondelete="SET NULL"),
            nullable=True,
        ),
    )


def downgrade() -> None:
    op.drop_column("pending_transactions", "account_id")
    op.drop_index("idx_merchant_aliases_user_id", table_name="merchant_aliases")
    op.drop_table("merchant_aliases")
