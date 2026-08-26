"""drop_profile_role

Fase 1.5 (keputusan user 2026-08-26): TIDAK ADA role admin di sistem ini —
semua user self-register via Supabase Auth. Kolom `role` (CHECK
'user'|'admin') beserta constraint `ck_profiles_role` di `public.profiles`
dihapus. Reset password ditangani Supabase Auth (recover/OTP ke email),
bukan lewat hak admin.

Revision ID: 0007
Revises: 0006
Create Date: 2026-08-26
"""

import sqlalchemy as sa

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_constraint("ck_profiles_role", "profiles", type_="check")
    op.drop_column("profiles", "role")


def downgrade() -> None:
    op.add_column(
        "profiles",
        sa.Column("role", sa.String(10), nullable=False, server_default="user"),
    )
    op.create_check_constraint("ck_profiles_role", "profiles", "role IN ('user', 'admin')")
