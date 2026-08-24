"""
Integration tests for the reports API (US-16).

Runs against the full FastAPI app via TestClient (same pattern as
test_health.py). Requires a running PostgreSQL.
"""

import uuid

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_RUN_ID = uuid.uuid4().hex[:8]


def _email(local: str) -> str:
    return f"{local}_{_RUN_ID}@example.com"


def _auth_headers() -> dict[str, str]:
    """Register + login a fresh user, return the Bearer header."""
    email = _email("report_api")
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "SecurePass1", "display_name": "Report API"},
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": "SecurePass1"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def test_summary_requires_auth():
    response = client.get("/api/reports/summary")
    assert response.status_code == 401


def test_summary_default_month():
    headers = _auth_headers()
    response = client.get("/api/reports/summary", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {
        "start_date",
        "end_date",
        "total_income",
        "total_expense",
        "net",
        "categories",
    }
    assert data["total_income"] == "0"
    assert data["total_expense"] == "0"
    assert data["net"] == "0"
    assert data["categories"] == []


def test_summary_valid_periods():
    headers = _auth_headers()
    for period in ("today", "week", "month", "last-month"):
        response = client.get(f"/api/reports/summary?period={period}", headers=headers)
        assert response.status_code == 200, period


def test_summary_invalid_period():
    headers = _auth_headers()
    response = client.get("/api/reports/summary?period=year", headers=headers)
    assert response.status_code == 422


def test_summary_custom_range():
    headers = _auth_headers()
    response = client.get(
        "/api/reports/summary",
        headers=headers,
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"},
    )
    assert response.status_code == 200
    assert response.json()["total_expense"] == "0"


def test_summary_custom_range_inverted():
    headers = _auth_headers()
    response = client.get(
        "/api/reports/summary",
        headers=headers,
        params={"start": "2026-02-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 422
