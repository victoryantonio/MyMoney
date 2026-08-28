"""transfer_and_account_type

Keputusan user 2026-08-28 (3 fitur + 1 tambahan):

1. `transactions.type` kini boleh `'transfer'` (selain income/expense).
   - `category_id` menjadi nullable — transfer TIDAK memakai kategori.
   - kolom baru `to_account_id` (FK accounts, nullable) = akun tujuan.
2. `accounts.bank_name` (teks bebas) diganti `account_type`
   ('cash' | 'ewallet' | 'bank') — keputusan user: hapus kolom lama.
   Migrasi data: bank_name IS NOT NULL → 'bank', sisanya 'cash'.
3. `idx_categories_user_name_type` menjadi PARTIAL (WHERE is_active = TRUE)
   supaya baris "shadow" per-user (is_active=FALSE, dipakai untuk
   menyembunyikan kategori default global milik semua user) tidak bentrok
   dengan kategori custom baru yang namanya sama.

Revision ID: 0008
Revises: 0007
Create Date: 2026-08-28
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    bind = op.get_bind()

    # ── 1. accounts: bank_name → account_type ────────────────────────────────
    op.add_column("accounts", sa.Column("account_type", sa.String(10), nullable=True))
    # Data migration: bank yang punya nama bank lama dianggap 'bank', sisanya 'cash'.
    bind.execute(sa.text("UPDATE accounts SET account_type = 'bank' WHERE bank_name IS NOT NULL"))
    bind.execute(sa.text("UPDATE accounts SET account_type = 'cash' WHERE account_type IS NULL"))
    op.alter_column(
        "accounts",
        "account_type",
        existing_type=sa.String(10),
        nullable=False,
        server_default=sa.text("'cash'"),
    )
    op.drop_column("accounts", "bank_name")
    op.create_check_constraint(
        "accounts_type_check",
        "accounts",
        "account_type IN ('cash', 'ewallet', 'bank')",
    )

    # ── 2. transactions: izinkan type 'transfer' ─────────────────────────────
    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('income', 'expense', 'transfer')",
    )
    op.alter_column(
        "transactions",
        "category_id",
        existing_type=UUID(as_uuid=True),
        nullable=True,
    )
    op.add_column(
        "transactions",
        sa.Column(
            "to_account_id",
            UUID(as_uuid=True),
            sa.ForeignKey("accounts.id"),
            nullable=True,
        ),
    )
    op.create_index("idx_transactions_to_account_id", "transactions", ["to_account_id"])

    # ── 3. categories: unique index partial (shadow per-user) ────────────────
    op.drop_index("idx_categories_user_name_type", table_name="categories")
    op.create_index(
        "idx_categories_user_name_type",
        "categories",
        [sa.text(f"COALESCE(user_id, '{_ZERO_UUID}')"), "name", "type"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    # ── 3. categories: kembalikan index non-partial ──────────────────────────
    op.drop_index("idx_categories_user_name_type", table_name="categories")
    op.create_index(
        "idx_categories_user_name_type",
        "categories",
        [sa.text(f"COALESCE(user_id, '{_ZERO_UUID}')"), "name", "type"],
        unique=True,
    )

    # ── 2. transactions: batalkan dukungan transfer ──────────────────────────
    op.drop_index("idx_transactions_to_account_id", table_name="transactions")
    op.drop_column("transactions", "to_account_id")
    op.alter_column(
        "transactions",
        "category_id",
        existing_type=UUID(as_uuid=True),
        nullable=False,
    )
    op.drop_constraint("transactions_type_check", "transactions", type_="check")
    op.create_check_constraint(
        "transactions_type_check",
        "transactions",
        "type IN ('income', 'expense')",
    )

    # ── 1. accounts: account_type → bank_name ────────────────────────────────
    op.drop_constraint("accounts_type_check", "accounts", type_="check")
    op.add_column("accounts", sa.Column("bank_name", sa.String(100), nullable=True))
    op.alter_column("accounts", "account_type", existing_type=sa.String(10), nullable=True)
    op.get_bind().execute(
        sa.text("UPDATE accounts SET bank_name = 'Bank' WHERE account_type = 'bank'")
    )
    op.drop_column("accounts", "account_type")
