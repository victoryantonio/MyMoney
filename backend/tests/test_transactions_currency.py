"""
Integration tests for the multi-currency feature (migrasi 0009).

- `original_currency` + `exchange_rate` tersimpan & kembali di response.
- Default 'IDR' / 1 untuk request lama (tanpa field currency).
- Normalisasi uppercase ('usd' → 'USD').
- Validasi: exchange_rate <= 0 → 422; panjang kode currency harus 3.
- PATCH semantics: update hanya exchange_rate, original_currency tetap.

Runs against the full FastAPI app via TestClient (same pattern as
test_transactions_pagination.py). Requires a running PostgreSQL.
"""

import uuid
from datetime import UTC, datetime

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skips in CI without creds)."""
    return supabase_factory


def _seed(headers: dict[str, str]) -> tuple[str, str]:
    """Buat satu kategori + satu akun; return (category_id, account_id)."""
    cat = client.post("/api/categories", json={"name": "Kurs", "type": "expense"}, headers=headers)
    assert cat.status_code == 201, cat.text
    acc = client.post("/api/accounts", json={"account_name": "Cash"}, headers=headers)
    assert acc.status_code == 201, acc.text
    return cat.json()["id"], acc.json()["id"]


def _tx_body(category_id: str, account_id: str, **overrides) -> dict:
    body = {
        "type": "expense",
        "total_amount": "100000.00",
        "category_id": category_id,
        "account_id": account_id,
        "merchant": "Kurs Belanja",
        "transaction_date": datetime(2026, 8, 28, tzinfo=UTC).isoformat(),
    }
    body.update(overrides)
    return body


def test_create_with_usd_currency(auth):
    headers = auth("cur_usd")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, original_currency="USD", exchange_rate="16250.00"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["original_currency"] == "USD"
    assert data["exchange_rate"] == "16250.000000"


def test_create_defaults_to_idr(auth):
    """Request tanpa field currency → IDR / 1 (kompatibilitas mundur)."""
    headers = auth("cur_idr")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()
    assert data["original_currency"] == "IDR"
    assert data["exchange_rate"] == "1.000000"


def test_create_normalizes_lowercase_currency(auth):
    headers = auth("cur_lower")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, original_currency="usd"),
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["original_currency"] == "USD"


def test_create_rejects_zero_exchange_rate(auth):
    headers = auth("cur_badrate")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, exchange_rate="0"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_create_rejects_negative_exchange_rate(auth):
    headers = auth("cur_negrate")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, exchange_rate="-1"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_create_rejects_bad_currency_length(auth):
    headers = auth("cur_badlen")
    cat_id, acc_id = _seed(headers)
    resp = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, original_currency="ID"),
        headers=headers,
    )
    assert resp.status_code == 422


def test_update_exchange_rate_patch(auth):
    headers = auth("cur_patch")
    cat_id, acc_id = _seed(headers)
    created = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id),
        headers=headers,
    ).json()
    # PATCH hanya exchange_rate — original_currency (IDR) tidak berubah.
    resp = client.put(
        f"/api/transactions/{created['id']}",
        json={"exchange_rate": "16250.00"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["original_currency"] == "IDR"
    assert data["exchange_rate"] == "16250.000000"


def test_update_currency_together(auth):
    headers = auth("cur_both")
    cat_id, acc_id = _seed(headers)
    created = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id),
        headers=headers,
    ).json()
    resp = client.put(
        f"/api/transactions/{created['id']}",
        json={"original_currency": "SGD", "exchange_rate": "12000.00"},
        headers=headers,
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["original_currency"] == "SGD"
    assert data["exchange_rate"] == "12000.000000"


def test_list_and_get_include_currency(auth):
    headers = auth("cur_list")
    cat_id, acc_id = _seed(headers)
    created = client.post(
        "/api/transactions",
        json=_tx_body(cat_id, acc_id, original_currency="MYR", exchange_rate="3500.00"),
        headers=headers,
    ).json()

    listed = client.get("/api/transactions", headers=headers).json()["items"]
    assert any(
        t["id"] == created["id"]
        and t["original_currency"] == "MYR"
        and t["exchange_rate"] == "3500.000000"
        for t in listed
    )

    got = client.get(f"/api/transactions/{created['id']}", headers=headers).json()
    assert got["original_currency"] == "MYR"
    assert got["exchange_rate"] == "3500.000000"


def test_currency_not_required_for_auth():
    resp = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "total_amount": "100.00",
            "account_id": str(uuid.uuid4()),
            "transaction_date": datetime(2026, 8, 28, tzinfo=UTC).isoformat(),
        },
    )
    assert resp.status_code == 401
