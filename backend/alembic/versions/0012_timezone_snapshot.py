"""timezone snapshot per transaksi + flag konfirmasi timezone profil

Revision ID: 0012
Revises: 0011
Create Date: 2026-09-20
"""

import sqlalchemy as sa

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Interpretasi tanggal/jam TIDAK dihitung ulang live: setiap transaksi
# menyimpan timezone yang berlaku saat transaksi itu dibuat/diinput. Jadi user
# boleh mengubah setelan timezone kapan pun tanpa menggeser transaksi lama.
# Storage tetap UTC (`transaction_date` sebagai timestamptz).
_DEFAULT_TZ = "Asia/Jakarta"


def upgrade() -> None:
    op.add_column(
        "transactions",
        sa.Column("timezone", sa.String(64), nullable=False, server_default=_DEFAULT_TZ),
    )
    # Backfill: transaksi lama memakai timezone profil saat ini (best-effort).
    op.execute(
        """
        UPDATE transactions AS t
           SET timezone = COALESCE(p.timezone, 'Asia/Jakarta')
          FROM profiles AS p
         WHERE p.id = t.user_id
        """
    )

    # false → user belum pernah memilih timezone secara eksplisit; aplikasi
    # menampilkan form timezone (default = timezone HP) saat pertama login.
    op.add_column(
        "profiles",
        sa.Column(
            "timezone_confirmed",
            sa.Boolean(),
            nullable=False,
            server_default=sa.text("false"),
        ),
    )


def downgrade() -> None:
    op.drop_column("profiles", "timezone_confirmed")
    op.drop_column("transactions", "timezone")
