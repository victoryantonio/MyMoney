"""
Integration tests for keyset pagination on GET /api/transactions (DATABASE.md §3.2).

The critical regression this guards: when many transactions share the same
transaction_date, the old `transaction_date <= cursor` filter skipped/duplicated
rows. The keyset (transaction_date, id) cursor must page through ALL rows
exactly once, regardless of ties.

Runs against the full FastAPI app via TestClient (same pattern as
test_reports_api.py). Requires a running PostgreSQL.
"""

import uuid
from datetime import UTC, datetime

from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_RUN_ID = uuid.uuid4().hex[:8]

# 25 transactions → 2 pages of 20 + 5.
_TOTAL = 25
_PAGE_SIZE = 20


def _email(local: str) -> str:
    return f"{local}_{_RUN_ID}@example.com"


def _auth_headers(local: str = "paging") -> dict[str, str]:
    """Register + login a fresh user, return the Bearer header."""
    email = _email(local)
    client.post(
        "/api/auth/register",
        json={"email": email, "password": "SecurePass1", "display_name": "Paging API"},
    )
    resp = client.post("/api/auth/login", json={"email": email, "password": "SecurePass1"})
    assert resp.status_code == 200
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


def _seed(headers: dict[str, str]) -> None:
    """Create one category + one account + 25 expense transactions.

    The first 10 transactions share the exact same transaction_date to prove
    the id tie-breaker works; the rest use distinct dates.
    """
    cat = client.post(
        "/api/categories", json={"name": "Paging", "type": "expense"}, headers=headers
    )
    assert cat.status_code == 201
    category_id = cat.json()["id"]

    acc = client.post("/api/accounts", json={"account_name": "Cash"}, headers=headers)
    assert acc.status_code == 201
    account_id = acc.json()["id"]

    base = datetime(2026, 8, 1, tzinfo=UTC)
    for i in range(_TOTAL):
        if i < 10:
            tx_date = base  # 10 rows on the SAME date
        else:
            tx_date = base.replace(day=2) if i < 20 else base.replace(day=3)
        resp = client.post(
            "/api/transactions",
            json={
                "type": "expense",
                "total_amount": f"{1000 + i}.00",
                "category_id": category_id,
                "account_id": account_id,
                "merchant": f"Shop {i}",
                "transaction_date": tx_date.isoformat(),
            },
            headers=headers,
        )
        assert resp.status_code == 201, resp.text


def test_pagination_requires_auth():
    resp = client.get("/api/transactions")
    assert resp.status_code == 401


def test_keyset_pagination_covers_all_rows_exactly_once():
    headers = _auth_headers()
    _seed(headers)

    seen_ids: list[str] = []
    cursor: str | None = None
    pages = 0
    total_count = None

    while True:
        params = {"cursor": cursor} if cursor else {}
        resp = client.get("/api/transactions", params=params, headers=headers)
        assert resp.status_code == 200
        data = resp.json()
        total_count = data["total_count"]

        items = data["items"]
        assert len(items) <= _PAGE_SIZE
        for item in items:
            assert item["id"] not in seen_ids, f"duplicate id across pages: {item['id']}"
            seen_ids.append(item["id"])

        pages += 1
        cursor = data["next_cursor"]
        if not cursor:
            break
        assert pages < 10, "pagination did not terminate"

    assert total_count == _TOTAL
    assert len(seen_ids) == _TOTAL
    assert pages == 2  # 20 + 5

    # Global keyset order across pages: (transaction_date DESC, id DESC).
    # Collect (date, id) of every row and assert strict descending order —
    # this fails if a page boundary skips or duplicates rows on date ties.
    rows: list[tuple[datetime, str]] = []
    cursor = None
    while True:
        params = {"cursor": cursor} if cursor else {}
        data = client.get("/api/transactions", params=params, headers=headers).json()
        for item in data["items"]:
            rows.append((datetime.fromisoformat(item["transaction_date"]), item["id"]))
        cursor = data["next_cursor"]
        if not cursor:
            break

    assert len(rows) == _TOTAL
    for prev, nxt in zip(rows, rows[1:]):
        assert prev > nxt, f"keyset order violated: {prev} not after {nxt}"


def test_legacy_timestamp_cursor_still_works():
    """A bare ISO-timestamp cursor (old format) must not error."""
    headers = _auth_headers("paging_legacy")
    _seed(headers)

    resp = client.get("/api/transactions", headers=headers)
    assert resp.status_code == 200
    first = resp.json()["items"][0]
    ts = first["transaction_date"]

    resp2 = client.get("/api/transactions", params={"cursor": ts}, headers=headers)
    assert resp2.status_code == 200
    assert resp2.json()["total_count"] == _TOTAL


def test_invalid_cursor_ignored():
    headers = _auth_headers("paging_invalid")
    _seed(headers)

    resp = client.get(
        "/api/transactions", params={"cursor": "not-a-date|not-a-uuid"}, headers=headers
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == _PAGE_SIZE
