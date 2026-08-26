"""
Integration tests for the reports API (US-16).

Runs against the full FastAPI app via TestClient (same pattern as
test_health.py). Requires a running PostgreSQL.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skips in CI without creds)."""
    return supabase_factory


def test_summary_requires_auth():
    response = client.get("/api/reports/summary")
    assert response.status_code == 401


def test_summary_default_month(auth):
    headers = auth()
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


def test_summary_valid_periods(auth):
    headers = auth()
    for period in ("today", "week", "month", "last-month"):
        response = client.get(f"/api/reports/summary?period={period}", headers=headers)
        assert response.status_code == 200, period


def test_summary_invalid_period(auth):
    headers = auth()
    response = client.get("/api/reports/summary?period=year", headers=headers)
    assert response.status_code == 422


def test_summary_custom_range(auth):
    headers = auth()
    response = client.get(
        "/api/reports/summary",
        headers=headers,
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-02-01T00:00:00Z"},
    )
    assert response.status_code == 200
    assert response.json()["total_expense"] == "0"


def test_summary_custom_range_inverted(auth):
    headers = auth()
    response = client.get(
        "/api/reports/summary",
        headers=headers,
        params={"start": "2026-02-01T00:00:00Z", "end": "2026-01-01T00:00:00Z"},
    )
    assert response.status_code == 422


# ── /api/reports/trend ───────────────────────────────────────────────────────


def test_trend_requires_auth():
    response = client.get("/api/reports/trend")
    assert response.status_code == 401


def test_trend_default_month_returns_points(auth):
    headers = auth()
    response = client.get("/api/reports/trend", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert set(data) == {"start_date", "end_date", "points"}
    assert isinstance(data["points"], list)
    # January defaults to this month → 28..31 points, all zero-filled.
    assert 28 <= len(data["points"]) <= 31
    first = data["points"][0]
    assert set(first) == {"date", "income", "expense"}


def test_trend_custom_range_zero_filled(auth):
    headers = auth()
    response = client.get(
        "/api/reports/trend",
        headers=headers,
        params={"start": "2026-01-01T00:00:00Z", "end": "2026-01-05T00:00:00Z"},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["points"]) == 4
    assert all(p["income"] == "0" and p["expense"] == "0" for p in data["points"])


def test_trend_invalid_period(auth):
    headers = auth()
    response = client.get("/api/reports/trend?period=year", headers=headers)
    assert response.status_code == 422
