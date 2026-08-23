"""
Integration tests for the authentication endpoints.

These tests run against the full FastAPI app using TestClient (synchronous WSGI adapter).
They require a running PostgreSQL database; in CI this is provided by the GitHub Actions
postgres service container.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


# ── /health ────────────────────────────────────────────────────────────────────

def test_health_check():
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


# ── /api/auth/register ─────────────────────────────────────────────────────────

def test_register_success():
    response = client.post("/api/auth/register", json={
        "email": "test_register@example.com",
        "password": "SecurePass1",
        "display_name": "Test User",
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "test_register@example.com"
    assert "id" in data
    assert "password_hash" not in data


def test_register_duplicate_email():
    payload = {"email": "dup@example.com", "password": "SecurePass1", "display_name": "Dup"}
    client.post("/api/auth/register", json=payload)  # first registration
    response = client.post("/api/auth/register", json=payload)  # duplicate
    assert response.status_code == 409


def test_register_weak_password():
    response = client.post("/api/auth/register", json={
        "email": "weak@example.com",
        "password": "onlyletters",
        "display_name": "Weak",
    })
    assert response.status_code == 422


# ── /api/auth/login ───────────────────────────────────────────────────────────

def test_login_success():
    # Register first
    client.post("/api/auth/register", json={
        "email": "login_test@example.com",
        "password": "SecurePass1",
        "display_name": "Login User",
    })
    response = client.post("/api/auth/login", json={
        "email": "login_test@example.com",
        "password": "SecurePass1",
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert "refresh_token" in data
    assert data["token_type"] == "bearer"


def test_login_wrong_password():
    client.post("/api/auth/register", json={
        "email": "wrongpw@example.com",
        "password": "SecurePass1",
        "display_name": "WP User",
    })
    response = client.post("/api/auth/login", json={
        "email": "wrongpw@example.com",
        "password": "WrongPassword9",
    })
    assert response.status_code == 401


def test_login_nonexistent_user():
    response = client.post("/api/auth/login", json={
        "email": "nobody@example.com",
        "password": "AnyPass1",
    })
    assert response.status_code == 401


# ── /api/auth/me ──────────────────────────────────────────────────────────────

def test_get_me_authenticated():
    # Register + login
    client.post("/api/auth/register", json={
        "email": "me_test@example.com",
        "password": "SecurePass1",
        "display_name": "Me User",
    })
    login_resp = client.post("/api/auth/login", json={
        "email": "me_test@example.com",
        "password": "SecurePass1",
    })
    token = login_resp.json()["access_token"]

    response = client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 200
    assert response.json()["email"] == "me_test@example.com"


def test_get_me_unauthenticated():
    response = client.get("/api/auth/me")
    assert response.status_code == 401
