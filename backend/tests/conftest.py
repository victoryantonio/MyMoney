"""
Shared pytest fixtures/config.

- Disables the slowapi rate limiter so test requests aren't throttled.
- Prepares the test database once (auth schema + auth.users mimic, then
  `alembic upgrade head`) so the suite is self-contained on a fresh local
  Postgres (CI) and idempotent on Supabase (local dev).
- Provides `db` / `profile` fixtures for service-layer tests.
- Provides `supabase_factory` for API tests that need a real Supabase JWT;
  those tests skip automatically when Supabase credentials are absent (CI).
"""

import os
import uuid
from pathlib import Path

import pytest
from dotenv import load_dotenv
from sqlalchemy import text

from app.core.rate_limit import limiter

limiter.enabled = False

_BACKEND_DIR = Path(__file__).resolve().parent.parent

# Muat .env dari root proyek agar SUPABASE_* tersedia untuk supabase_factory
# saat dijalankan lokal (di CI variabel disuntik langsung via env GitHub Actions).
load_dotenv(_BACKEND_DIR.parent / ".env")


@pytest.fixture(scope="session", autouse=True)
def _prepared_database():
    """Ensure the `auth` schema + a minimal `auth.users` mimic exist, then run migrations.

    On Supabase the mimic is a no-op (schema + table already exist); on a plain
    local Postgres (CI) it gives migration 0005/0006 the FK target they need.
    """
    from alembic import command
    from alembic.config import Config
    from app.db.session import engine

    with engine.begin() as conn:
        conn.execute(text("CREATE SCHEMA IF NOT EXISTS auth"))
        # Di Supabase auth.users sudah dikelola Supabase; role postgres tidak
        # punya izin CREATE di schema auth. Cek keberadaan dulu — hanya buat
        # mimic jika belum ada (CI: Postgres lokal kosong).
        exists = conn.execute(text("SELECT to_regclass('auth.users') IS NOT NULL")).scalar()
        if not exists:
            conn.execute(
                text(
                    "CREATE TABLE auth.users ("
                    " id uuid PRIMARY KEY,"
                    " email text,"
                    " created_at timestamptz DEFAULT now())"
                )
            )

    cfg = Config(str(_BACKEND_DIR / "alembic.ini"))
    cfg.set_main_option("script_location", str(_BACKEND_DIR / "alembic"))
    command.upgrade(cfg, "head")


@pytest.fixture
def db():
    from app.db.session import SessionLocal

    session = SessionLocal()
    yield session
    session.close()


@pytest.fixture
def profile(db):
    """Create an auth.users row + profiles row and return the Profile.

    On Supabase the `on_auth_user_created` trigger auto-creates the profile;
    on the local mirror (no trigger) we create it explicitly. The row is
    deleted on teardown (CASCADE removes dependent test data).
    """
    from app.models.profile import Profile

    pid = uuid.uuid4()
    db.execute(text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": pid})
    db.commit()

    p = db.get(Profile, pid)
    if p is None:  # local mirror without the Supabase trigger
        p = Profile(id=pid, display_name="Test Profile")
        db.add(p)
        db.commit()
        db.refresh(p)

    yield p

    db.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": pid})
    db.commit()


@pytest.fixture(scope="session")
def supabase_factory():
    """Return a factory that creates a fresh Supabase user and returns its Bearer headers.

    Skips the test when SUPABASE_* credentials are not configured (CI).
    """
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    anon = os.environ.get("SUPABASE_ANON_KEY", "")
    service = os.environ.get("SUPABASE_SERVICE_ROLE_KEY", "")
    if not (url and anon and service):
        pytest.skip("SUPABASE_URL / SUPABASE_ANON_KEY / SUPABASE_SERVICE_ROLE_KEY not set")

    import httpx

    def _factory(prefix: str = "apitest") -> dict[str, str]:
        email = f"{prefix}_{uuid.uuid4().hex[:10]}@mymoney.dev"
        password = "SecurePass1"
        headers = {"apikey": service, "Authorization": f"Bearer {service}"}
        resp = httpx.post(
            f"{url}/auth/v1/admin/users",
            json={"email": email, "password": password, "email_confirm": True},
            headers=headers,
        )
        resp.raise_for_status()
        resp = httpx.post(
            f"{url}/auth/v1/token?grant_type=password",
            json={"email": email, "password": password},
            headers={"apikey": anon},
        )
        resp.raise_for_status()
        return {"Authorization": f"Bearer {resp.json()['access_token']}"}

    return _factory
