"""
API tests for Telegram account linking (Fase 2 rebuild).

  - GET /api/telegram/link?token=... serves the HTML form (valid token) or 400 (invalid)
  - POST /api/telegram/link/confirm creates the TelegramLink mapping
  - relink semantics: one telegram_id ↔ one profile

Supabase JWT verification is mocked — the JWKS network call must never run
inside unit tests.
"""

import uuid
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select, text

from app.core.config import settings
from app.core.security import SupabaseJWTError, create_telegram_link_token
from app.main import app
from app.models.profile import Profile
from app.models.telegram_link import TelegramLink

client = TestClient(app)


def _make_link_token(telegram_id: int) -> str:
    return create_telegram_link_token(telegram_id)


def _make_profile(db, display_name: str = "Other User") -> Profile:
    pid = uuid.uuid4()
    db.execute(text("INSERT INTO auth.users (id) VALUES (:id)"), {"id": pid})
    db.commit()
    p = db.get(Profile, pid)
    if p is None:  # local mirror without the Supabase trigger
        p = Profile(id=pid, display_name=display_name)
        db.add(p)
        db.commit()
        db.refresh(p)
    return p


@pytest.fixture
def jwt_secret():
    """Pin the legacy JWT secret for the whole test so created tokens decode."""
    with patch.object(settings, "jwt_secret_key", "test-secret"):
        yield


@pytest.fixture
def link_token(jwt_secret) -> str:
    return _make_link_token(123456789)


# ── GET /api/telegram/link ────────────────────────────────────────────────────


def test_link_page_valid_token(link_token):
    resp = client.get(f"/api/telegram/link?token={link_token}")
    assert resp.status_code == 200
    assert "Link your Telegram account" in resp.text


def test_link_page_invalid_token():
    resp = client.get("/api/telegram/link?token=not-a-jwt")
    assert resp.status_code == 400
    assert "expired" in resp.json()["detail"].lower()


# ── POST /api/telegram/link/confirm ───────────────────────────────────────────


def test_confirm_invalid_link_token():
    resp = client.post(
        "/api/telegram/link/confirm",
        json={"link_token": "not-a-jwt", "access_token": "anything"},
    )
    assert resp.status_code == 400


def test_confirm_success(link_token, profile, db):
    with patch("app.api.telegram_linking.verify_supabase_jwt", return_value=str(profile.id)):
        resp = client.post(
            "/api/telegram/link/confirm",
            json={"link_token": link_token, "access_token": "fake-supabase-jwt"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"ok": True}

    row = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == 123456789))
    assert row is not None
    assert row.user_id == profile.id


def test_confirm_idempotent(link_token, profile, db):
    """Linking the same telegram_id to the same user twice stays a single row."""
    db.add(TelegramLink(id=uuid.uuid4(), user_id=profile.id, telegram_id=123456789))
    db.commit()

    with patch("app.api.telegram_linking.verify_supabase_jwt", return_value=str(profile.id)):
        resp = client.post(
            "/api/telegram/link/confirm",
            json={"link_token": link_token, "access_token": "fake"},
        )
    assert resp.status_code == 200

    rows = db.scalars(select(TelegramLink).where(TelegramLink.telegram_id == 123456789)).all()
    assert len(rows) == 1


def test_confirm_account_not_found(link_token):
    with patch("app.api.telegram_linking.verify_supabase_jwt", return_value=str(uuid.uuid4())):
        resp = client.post(
            "/api/telegram/link/confirm",
            json={"link_token": link_token, "access_token": "fake"},
        )
    assert resp.status_code == 400
    assert "not found" in resp.json()["detail"].lower()


def test_confirm_invalid_supabase_token(link_token, profile):
    with patch(
        "app.api.telegram_linking.verify_supabase_jwt",
        side_effect=SupabaseJWTError("bad token"),
    ):
        resp = client.post(
            "/api/telegram/link/confirm",
            json={"link_token": link_token, "access_token": "bad"},
        )
    assert resp.status_code == 401


def test_confirm_relink_telegram_id(link_token, profile, db):
    """A telegram_id owned by another user is moved to the new linker."""
    other = _make_profile(db)
    db.add(TelegramLink(id=uuid.uuid4(), user_id=other.id, telegram_id=123456789))
    db.commit()

    with patch("app.api.telegram_linking.verify_supabase_jwt", return_value=str(profile.id)):
        resp = client.post(
            "/api/telegram/link/confirm",
            json={"link_token": link_token, "access_token": "fake"},
        )
    assert resp.status_code == 200

    row = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == 123456789))
    assert row is not None
    assert row.user_id == profile.id
    # the previous owner no longer holds any link
    assert db.scalar(select(TelegramLink).where(TelegramLink.user_id == other.id)) is None

    db.execute(text("DELETE FROM auth.users WHERE id = :id"), {"id": other.id})
    db.commit()
