"""currency_and_category_ci_name

Keputusan user 2026-08-28 (fitur currency + jaminan kategori unik):

1. Currency (multi mata uang, IDR sebagai base):
   - `transactions.original_currency` (ISO 4217, default 'IDR') = mata uang
     yang dipilih user saat input.
   - `transactions.exchange_rate` (Numeric, default 1) = 1 unit
     original_currency berapa IDR. `total_amount` TETAP disimpan dalam IDR
     (basis laporan/saldo), sehingga semua agregasi existing tidak berubah.
   - Klien menghitung `total_amount = nominal × exchange_rate` (rate
     diambil dari open.er-api.com saat user memilih mata uang non-IDR).

2. Nama kategori unik per user — sekarang case-INSENSITIVE di level DB:
   index `idx_categories_user_name_type` diubah dari `name` menjadi
   `lower(name)`, sehingga 'Kuliner' dan 'kuliner' milik user yang sama
   (type sama) tidak bisa dibuat — sebelumnya hanya API yang mencegah
   (case-insensitive), DB masih case-sensitive.

Revision ID: 0009
Revises: 0008
Create Date: 2026-08-28
"""

import sqlalchemy as sa

from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

_ZERO_UUID = "00000000-0000-0000-0000-000000000000"


def upgrade() -> None:
    # ── 1. transactions: kolom currency ──────────────────────────────────────
    op.add_column(
        "transactions",
        sa.Column("original_currency", sa.String(3), nullable=False, server_default="IDR"),
    )
    op.add_column(
        "transactions",
        sa.Column("exchange_rate", sa.Numeric(18, 6), nullable=False, server_default="1"),
    )
    op.create_check_constraint(
        "transactions_currency_length",
        "transactions",
        "char_length(original_currency) = 3",
    )
    op.create_check_constraint(
        "transactions_exchange_rate_positive",
        "transactions",
        "exchange_rate > 0",
    )

    # ── 2. categories: nama unik per user, case-insensitive ──────────────────
    # Data cleanup: jika sudah ada duplikat case-insensitive yang aktif
    # (mis. 'Kuliner' + 'kuliner' milik user yang sama), nonaktifkan semua
    # kecuali yang paling awal — supaya create unique index tidak gagal.
    bind = op.get_bind()
    bind.execute(
        sa.text(
            """
            UPDATE categories SET is_active = FALSE
            WHERE id IN (
                SELECT id FROM (
                    SELECT id,
                           ROW_NUMBER() OVER (
                               PARTITION BY COALESCE(user_id::text, :zero_uuid),
                                            lower(name), type
                               ORDER BY created_at ASC, id ASC
                           ) AS rn
                    FROM categories
                    WHERE is_active = TRUE
                ) ranked
                WHERE rn > 1
            )
            """
        ),
        {"zero_uuid": _ZERO_UUID},
    )
    op.drop_index("idx_categories_user_name_type", table_name="categories")
    op.create_index(
        "idx_categories_user_name_type",
        "categories",
        [sa.text(f"COALESCE(user_id, '{_ZERO_UUID}')"), sa.text("lower(name)"), "type"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )


def downgrade() -> None:
    # ── 2. categories: kembalikan index case-sensitive ──────────────────────
    op.drop_index("idx_categories_user_name_type", table_name="categories")
    op.create_index(
        "idx_categories_user_name_type",
        "categories",
        [sa.text(f"COALESCE(user_id, '{_ZERO_UUID}')"), "name", "type"],
        unique=True,
        postgresql_where=sa.text("is_active = TRUE"),
    )

    # ── 1. transactions: hapus kolom currency ───────────────────────────────
    op.drop_constraint("transactions_exchange_rate_positive", "transactions", type_="check")
    op.drop_constraint("transactions_currency_length", "transactions", type_="check")
    op.drop_column("transactions", "exchange_rate")
    op.drop_column("transactions", "original_currency")
