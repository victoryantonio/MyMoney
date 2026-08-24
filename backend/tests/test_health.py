"""
Integration tests for the authentication endpoints.

These tests run against the full FastAPI app using TestClient (synchronous WSGI adapter).
They require a running PostgreSQL database; in CI this is provided by the GitHub Actions
postgres service container.

NOTE: They run against a shared database, so emails are suffixed with a
per-run unique token to stay isolated across runs.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_RUN_ID = uuid.uuid4().hex[:8]


def _email(local: str) -> str:
    return f"{local}_{_RUN_ID}@example.com"


# ── /health ────────────────────────────────────────────────────────────────────


def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── /api/auth/register ─────────────────────────────────────────────────────────


def test_register_success():
    response = client.post(
        "/api/auth/register",
        json={
            "email": _email("test_register"),
            "password": "SecurePass1",
            "display_name": "Test User",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == _email("test_register")
    assert "id" in data
    assert "password_hash" not in data


def test_register_duplicate_email():
    payload = {"email": _email("dup"), "password": "SecurePass1", "display_name": "Dup"}
    client.post("/api/auth/register", json=payload)  # first registration
    response = client.post("/api/auth/register", json=payload)  # duplicate
    assert response.status_code == 409


def test_register_weak_password():
    response = client.post(
        "/api/auth/register",
        json={
            "email": _email("weak"),
            "password": "onlyletters",
            "display_name": "Weak",
        },
    )
    assert response.status_code == 422


# ── /api/auth/login ───────────────────────────────────────────────────────────


def test_login_success():
    # Register first
    client.post(
        "/api/auth/register",
        json={
            "email": _email("login_test"),
            "password": "SecurePass1",
            "display_name": "Login User",
        },
    )
    response = client.post(
        "/api/auth/login",
        json={
            "email": _email("login_test"),
            "password": "SecurePass1",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client.post(
        "/api/auth/register",
        json={
            "email": _email("wrongpw"),
            "password": "SecurePass1",
            "display_name": "WP User",
        },
    )
    response = client.post(
        "/api/auth/login",
        json={
            "email": _email("wrongpw"),
            "password": "WrongPassword9",
        },
    )
    assert response.status_code == 401


def test_login_nonexistent_user():
    response = client.post(
        "/api/auth/login",
        json={
            "email": _email("nobody"),
            "password": "AnyPass1",
        },
    )
    assert response.status_code == 401


# ── /api/auth/me ──────────────────────────────────────────────────────────────


def test_get_me_authenticated():
    # Register + login
    client.post(
        "/api/auth/register",
        json={
            "email": _email("me_test"),
            "password": "SecurePass1",
            "display_name": "Me User",
        },
    )
    login_resp = client.post(
        "/api/auth/login",
        json={
            "email": _email("me_test"),
            "password": "SecurePass1",
        },
    )
    token = login_resp.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == _email("me_test")


def test_get_me_unauthenticated():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
