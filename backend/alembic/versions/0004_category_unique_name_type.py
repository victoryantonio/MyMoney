"""category_unique_name_type

Adds the documented unique index `idx_categories_user_name_type`
(DATABASE.md §2.3): (COALESCE(user_id, zero-uuid), name, type) must be unique,
preventing duplicate category names per user (and per global default set).

Self-healing: during development the shared dev DB accumulated duplicate
*global* category rows (test fixtures created new global Food/Transport/Salary
rows on every run). Before creating the index we merge those duplicates —
keeping the canonical (earliest `created_at`, then `id`) row — and re-point
`transactions.category_id` / `pending_transactions.category_id` at the kept
row so no FK reference breaks.

Revision ID: 0004
Revises: 0003
Create Date: 2026-08-24
"""

import sqlalchemy as sa

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None

# Sentinel for global categories (user_id IS NULL), matching DATABASE.md §2.3.
_ZERO_UUID = "00000000-0000-0000-0000-000000000000"

# Shared window: rank rows within (owner, name, type); rn = 1 is the keeper.
_RANK_SQL = """
    SELECT id,
           COALESCE(user_id, :zero) AS owner,
           name,
           type,
           ROW_NUMBER() OVER (
               PARTITION BY COALESCE(user_id, :zero), name, type
               ORDER BY created_at ASC, id ASC
           ) AS rn
    FROM categories
"""

_REPOINT_SQL = """
    UPDATE {table}
    SET category_id = keep.keep_id
    FROM (
        SELECT d.id AS dup_id, k.id AS keep_id
        FROM ({rank}) d
        JOIN ({rank}) k
          ON k.owner = d.owner
         AND k.name = d.name
         AND k.type = d.type
         AND k.rn = 1
        WHERE d.rn > 1
    ) keep
    WHERE {table}.category_id = keep.dup_id
"""


def upgrade() -> None:
    bind = op.get_bind()

    # 1. Re-point transactions referencing a duplicate category to the keeper.
    bind.execute(
        sa.text(_REPOINT_SQL.format(table="transactions", rank=_RANK_SQL)), {"zero": _ZERO_UUID}
    )

    # 2. Same for pending_transactions.
    bind.execute(
        sa.text(_REPOINT_SQL.format(table="pending_transactions", rank=_RANK_SQL)),
        {"zero": _ZERO_UUID},
    )

    # 3. Delete the duplicate category rows themselves.
    bind.execute(
        sa.text(
            """
            DELETE FROM categories c
            USING (
                SELECT id,
                       ROW_NUMBER() OVER (
                           PARTITION BY COALESCE(user_id, :zero), name, type
                           ORDER BY created_at ASC, id ASC
                       ) AS rn
                FROM categories
            ) ranked
            WHERE c.id = ranked.id
              AND ranked.rn > 1
            """
        ),
        {"zero": _ZERO_UUID},
    )

    # 4. The documented unique index (DATABASE.md §2.3).
    op.create_index(
        "idx_categories_user_name_type",
        "categories",
        [
            sa.text(f"COALESCE(user_id, '{_ZERO_UUID}')"),
            "name",
            "type",
        ],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_categories_user_name_type", table_name="categories")
