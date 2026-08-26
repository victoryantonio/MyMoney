"""fk_profiles

Fase 1: pindahkan seluruh FK `user_id` dari tabel `users` (v1) ke `profiles` (v2).

Latar belakang (chain of thought):
- User v2 dibuat lewat Supabase Auth → hanya ada di `auth.users` + `profiles`.
- Tabel v1 (accounts, categories, transactions, audit_logs, telegram_links,
  pending_transactions) masih ber-FK ke `users.id` → insert untuk user v2
  gagal dengan ForeignKeyViolation (sudah dibuktikan empiris).
- Tabel `users` kosong (0 baris, hasil query) → aman di-drop.

Revision ID: 0006
Revises: 0005
Create Date: 2026-08-26
"""

import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None

# (table, constraint_name, column)
_FKS_TO_PROFILES = [
    ("telegram_links", "telegram_links_user_id_fkey", "user_id"),
    ("categories", "categories_user_id_fkey", "user_id"),
    ("accounts", "accounts_user_id_fkey", "user_id"),
    ("transactions", "transactions_user_id_fkey", "user_id"),
    ("audit_logs", "audit_logs_user_id_fkey", "user_id"),
    ("pending_transactions", "pending_transactions_user_id_fkey", "user_id"),
]


def upgrade() -> None:
    # 1) Drop FK lama ke users.id
    for table, fk, _col in _FKS_TO_PROFILES:
        op.drop_constraint(fk, table, type_="foreignkey")

    # 2) Drop tabel users (kosong — v2 memakai profiles)
    op.drop_index("idx_users_email", table_name="users")
    op.drop_table("users")

    # 3) Re-create FK ke profiles.id
    for table, fk, col in _FKS_TO_PROFILES:
        op.create_foreign_key(fk, table, "profiles", [col], ["id"], ondelete="CASCADE")


def downgrade() -> None:
    # 1) Drop FK baru ke profiles.id
    for table, fk, _col in _FKS_TO_PROFILES:
        op.drop_constraint(fk, table, type_="foreignkey")

    # 2) Re-create tabel users (struktur migration 0001)
    op.create_table(
        "users",
        sa.Column("id", UUID(as_uuid=True), primary_key=True),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Jakarta"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("idx_users_email", "users", ["email"], unique=True)

    # 3) Re-create FK lama ke users.id
    for table, fk, col in _FKS_TO_PROFILES:
        op.create_foreign_key(fk, table, "users", [col], ["id"], ondelete="CASCADE")
