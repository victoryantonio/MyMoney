"""tanggal transaksi asli pada pending_transactions

Revision ID: 0013
Revises: 0012
Create Date: 2026-10-30

Latar belakang: alur "Matching Mutasi" menyimpan baris mutasi bank yang belum
cocok sebagai `pending_transactions`. Sebelum revisi ini tanggal+jam mutasi
hanya ditulis sebagai teks di kolom `note`, sehingga saat user mengonfirmasi
transaksi selalu tercatat pada waktu konfirmasi (hari ini). Kolom di bawah
menyimpan tanggal+jam ASLI dari mutasi agar dipakai apa adanya saat konfirmasi.

`transaction_date` disimpan UTC (timestamptz) dan `timezone` menyimpan zona
waktu yang dipakai saat tanggal mutasi ditafsirkan — pola yang sama dengan
tabel `transactions`.
"""

import sqlalchemy as sa

from alembic import op

revision = "0013"
down_revision = "0012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "pending_transactions",
        sa.Column("transaction_date", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "pending_transactions",
        sa.Column("timezone", sa.String(64), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("pending_transactions", "timezone")
    op.drop_column("pending_transactions", "transaction_date")
