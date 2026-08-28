"""
Integration tests for server-side sorting on GET /api/transactions.

Guards the two reported bugs:
1. Sort by nominal must be instant (server-side), not client-side fetch-all.
2. Switching sort must never return an empty page incorrectly — keyset
   cursors must match the requested ORDER BY.

Mirrors the pattern of test_transactions_pagination.py (DATABASE.md §3.2):
runs against the full FastAPI app via TestClient; requires PostgreSQL.
"""

from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)

_TOTAL = 25
_PAGE_SIZE = 20


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skips in CI without creds)."""
    return supabase_factory


def _seed(headers: dict[str, str]) -> None:
    """One category + one account + 25 expense transactions.

    Amounts are 1000..1024 (unique), dates: first 10 share 2026-08-01,
    next 10 on 2026-08-02, last 5 on 2026-08-03.
    """
    cat = client.post(
        "/api/categories", json={"name": "Sorting", "type": "expense"}, headers=headers
    )
    assert cat.status_code == 201
    category_id = cat.json()["id"]

    acc = client.post("/api/accounts", json={"account_name": "Cash"}, headers=headers)
    assert acc.status_code == 201
    account_id = acc.json()["id"]

    base = datetime(2026, 8, 1, tzinfo=UTC)
    for i in range(_TOTAL):
        tx_date = base if i < 10 else base.replace(day=2) if i < 20 else base.replace(day=3)
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


def _amounts(headers: dict[str, str], sort: str) -> list[float]:
    """Fetch all pages of `sort` and return the ordered total_amounts."""
    amounts: list[float] = []
    cursor: str | None = None
    while True:
        params = {"sort": sort}
        if cursor:
            params["cursor"] = cursor
        data = client.get("/api/transactions", params=params, headers=headers).json()
        amounts.extend(float(item["total_amount"]) for item in data["items"])
        cursor = data["next_cursor"]
        if not cursor:
            break
    return amounts


def test_largest_orders_by_amount_desc(auth):
    headers = auth("sort_largest")
    _seed(headers)
    amounts = _amounts(headers, "largest")
    assert amounts == sorted(amounts, reverse=True)
    assert amounts[0] == 1024.0 and amounts[-1] == 1000.0
    assert len(amounts) == _TOTAL


def test_smallest_orders_by_amount_asc(auth):
    headers = auth("sort_smallest")
    _seed(headers)
    amounts = _amounts(headers, "smallest")
    assert amounts == sorted(amounts)
    assert amounts[0] == 1000.0 and amounts[-1] == 1024.0
    assert len(amounts) == _TOTAL


def test_oldest_orders_by_date_asc(auth):
    headers = auth("sort_oldest")
    _seed(headers)
    data = client.get("/api/transactions", params={"sort": "oldest"}, headers=headers).json()
    dates = [item["transaction_date"] for item in data["items"]]
    # First page: all 2026-08-01 rows then 2026-08-02 rows (10 + 10).
    assert dates[0].startswith("2026-08-01")
    assert len(dates) == _PAGE_SIZE


def test_newest_is_default(auth):
    headers = auth("sort_newest_default")
    _seed(headers)
    explicit = client.get(
        "/api/transactions", params={"sort": "newest"}, headers=headers
    ).json()["items"]
    implicit = client.get("/api/transactions", headers=headers).json()["items"]
    assert [i["id"] for i in explicit] == [i["id"] for i in implicit]


def test_amount_pagination_covers_all_exactly_once(auth):
    """Keyset cursor for amount sorts must not skip/duplicate across pages."""
    headers = auth("sort_amount_page")
    _seed(headers)

    seen_ids: list[str] = []
    cursor: str | None = None
    pages = 0
    while True:
        params = {"sort": "largest"}
        if cursor:
            params["cursor"] = cursor
        data = client.get("/api/transactions", params=params, headers=headers).json()
        for item in data["items"]:
            assert item["id"] not in seen_ids, f"duplicate id: {item['id']}"
            seen_ids.append(item["id"])
        pages += 1
        cursor = data["next_cursor"]
        if not cursor:
            break
        assert pages < 10

    assert len(seen_ids) == _TOTAL
    assert pages == 2  # 20 + 5


def test_amount_cursor_is_ignored_for_date_sort(auth):
    """A cursor from an amount sort fed into a date sort must not 500 —
    it is treated as an invalid cursor (ignored → restart from beginning)."""
    headers = auth("sort_mixed_cursor")
    _seed(headers)

    # Get an amount-sort cursor, then reuse it on the default date sort.
    data = client.get(
        "/api/transactions", params={"sort": "largest"}, headers=headers
    ).json()
    amount_cursor = data["next_cursor"]
    assert amount_cursor

    resp = client.get(
        "/api/transactions",
        params={"cursor": amount_cursor, "sort": "newest"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == _PAGE_SIZE


def test_invalid_amount_cursor_ignored(auth):
    headers = auth("sort_invalid_cursor")
    _seed(headers)
    resp = client.get(
        "/api/transactions",
        params={"sort": "largest", "cursor": "not-a-number|not-a-uuid"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert len(resp.json()["items"]) == _PAGE_SIZE
