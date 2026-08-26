"""supabase_profiles

Stack v2 (Fase 0): menambahkan tabel `public.profiles` (pengganti `users`
sebagai tabel user aplikasi, relasi 1:1 dengan `auth.users` milik Supabase),
trigger `on_auth_user_created` (auto-create profile saat user register via
Supabase Auth), dan RLS dasar (DATABASE.md §2.1, §10).

IMPORTANT: migration ini TARGET Supabase Postgres — tabel `auth.users` dan
schema `auth` harus sudah ada (disediakan Supabase). Jangan jalankan terhadap
Postgres lokal/docker tanpa schema `auth`.

Revision ID: 0005
Revises: 0004
Create Date: 2026-08-26
"""

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects.postgresql import UUID

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── profiles (v2 user table, 1:1 dengan auth.users) ───────────────────────
    op.create_table(
        "profiles",
        sa.Column(
            "id",
            UUID(as_uuid=True),
            sa.ForeignKey("auth.users.id", ondelete="CASCADE"),
            primary_key=True,
        ),
        sa.Column("display_name", sa.String(100), nullable=False),
        sa.Column("role", sa.String(10), nullable=False, server_default="user"),
        sa.Column("timezone", sa.String(50), nullable=False, server_default="Asia/Jakarta"),
        sa.Column("is_active", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_check_constraint(
        "ck_profiles_role", "profiles", "role IN ('user', 'admin')"
    )

    # ── Trigger: auto-create profile saat user register ───────────────────────
    op.execute(
        """
        CREATE OR REPLACE FUNCTION public.handle_new_user()
        RETURNS TRIGGER AS $$
        BEGIN
          INSERT INTO public.profiles (id, display_name)
          VALUES (NEW.id, COALESCE(NEW.raw_user_meta_data->>'display_name', 'User'));
          RETURN NEW;
        END;
        $$ LANGUAGE plpgsql SECURITY DEFINER;
        """
    )
    op.execute(
        """
        CREATE TRIGGER on_auth_user_created
          AFTER INSERT ON auth.users
          FOR EACH ROW EXECUTE FUNCTION public.handle_new_user();
        """
    )

    # ── RLS dasar (DATABASE.md §10) ────────────────────────────────────────────
    for table in [
        "public.profiles",
        "public.transactions",
        "public.transaction_items",
        "public.accounts",
        "public.categories",
        "public.pending_transactions",
        "public.audit_logs",
    ]:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY;")

    op.execute(
        'CREATE POLICY "Users can view own profiles" ON public.profiles FOR SELECT '
        "USING (auth.uid() = id);"
    )
    op.execute(
        'CREATE POLICY "Users can update own profiles" ON public.profiles FOR UPDATE '
        "USING (auth.uid() = id) WITH CHECK (auth.uid() = id);"
    )
    op.execute(
        'CREATE POLICY "Users can view own transactions" ON public.transactions FOR SELECT '
        "USING (auth.uid() = user_id);"
    )
    op.execute(
        'CREATE POLICY "Users can insert own transactions" ON public.transactions FOR INSERT '
        "WITH CHECK (auth.uid() = user_id);"
    )
    op.execute(
        'CREATE POLICY "Users can view own transaction items" ON public.transaction_items FOR SELECT '
        "USING (EXISTS (SELECT 1 FROM public.transactions t WHERE t.id = transaction_id AND t.user_id = auth.uid()));"
    )
    op.execute(
        'CREATE POLICY "Users can view own accounts" ON public.accounts FOR SELECT '
        "USING (auth.uid() = user_id);"
    )
    op.execute(
        'CREATE POLICY "Users can view own or global categories" ON public.categories FOR SELECT '
        "USING (user_id = auth.uid() OR user_id IS NULL);"
    )


def downgrade() -> None:
    op.execute("DROP TRIGGER IF EXISTS on_auth_user_created ON auth.users;")
    op.execute("DROP FUNCTION IF EXISTS public.handle_new_user();")
    op.drop_table("profiles")
