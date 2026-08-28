"""
Integration tests for the accounts API (Fase 3.5).

Covers:
  - CRUD: create / list / get / update
  - Soft-delete via POST /{id}/deactivate — accounts can NEVER be hard-deleted
    (no DELETE endpoint exists; verify 405)
  - Balance is computed (initial_balance + SUM of transactions), never stored
  - Deactivation with non-zero balance REQUIRES a target account; the balance
    is moved via balancing "Transfer" transactions (DATABASE.md §2.4)
  - Inactive accounts are excluded from new-transaction input
    (CODING_RULES §2.8) — POST /api/transactions rejects them (422)

Runs against the full FastAPI app via TestClient (same pattern as
test_reports_api.py). Requires a running PostgreSQL.
"""

import pytest
from fastapi.testclient import TestClient

from app.main import app

client = TestClient(app)


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skips in CI without creds)."""
    return supabase_factory


def _create_account(headers, name="Cash", initial="0.00", acct_type="cash"):
    body = {"account_name": name, "initial_balance": initial, "account_type": acct_type}
    resp = client.post("/api/accounts", json=body, headers=headers)
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_transaction(headers, account_id, amount, tx_type="expense"):
    cat = client.post("/api/categories", json={"name": "Test", "type": tx_type}, headers=headers)
    assert cat.status_code == 201, cat.text
    resp = client.post(
        "/api/transactions",
        json={
            "type": tx_type,
            "total_amount": amount,
            "category_id": cat.json()["id"],
            "account_id": account_id,
            "transaction_date": "2026-08-01T00:00:00Z",
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth ─────────────────────────────────────────────────────────────────────


def test_list_requires_auth():
    assert client.get("/api/accounts").status_code == 401


# ── Create ────────────────────────────────────────────────────────────────────


def test_create_account(auth):
    headers = auth()
    acc = _create_account(headers, name="BCA", initial="50000.00", acct_type="bank")
    assert acc["account_name"] == "BCA"
    assert acc["account_type"] == "bank"
    assert acc["initial_balance"] == "50000.00"
    assert acc["current_balance"] == "50000.00"  # computed == initial (no tx yet)
    assert acc["is_active"] is True


def test_create_account_type_validation(auth):
    headers = auth()
    resp = client.post(
        "/api/accounts",
        json={"account_name": "X", "account_type": "saham"},
        headers=headers,
    )
    assert resp.status_code == 422


def test_create_account_validation(auth):
    headers = auth()
    resp = client.post("/api/accounts", json={"account_name": ""}, headers=headers)
    assert resp.status_code == 422
    resp = client.post(
        "/api/accounts",
        json={"account_name": "X", "initial_balance": "-1"},
        headers=headers,
    )
    assert resp.status_code == 422


# ── List ──────────────────────────────────────────────────────────────────────


def test_list_active_only_by_default(auth):
    headers = auth()
    _create_account(headers, name="Cash")
    bca = _create_account(headers, name="BCA")
    client.post(f"/api/accounts/{bca['id']}/deactivate", json={}, headers=headers)
    lst = client.get("/api/accounts", headers=headers)
    assert lst.status_code == 200
    names = [a["account_name"] for a in lst.json()]
    assert "Cash" in names and "BCA" not in names


def test_list_include_inactive(auth):
    headers = auth()
    _create_account(headers, name="Cash")
    bca = _create_account(headers, name="BCA")
    client.post(f"/api/accounts/{bca['id']}/deactivate", json={}, headers=headers)
    lst = client.get("/api/accounts?include_inactive=true", headers=headers)
    assert lst.status_code == 200
    accounts = lst.json()
    names = [a["account_name"] for a in accounts]
    assert "Cash" in names and "BCA" in names
    assert next(a for a in accounts if a["account_name"] == "BCA")["is_active"] is False


# ── Get / Update ──────────────────────────────────────────────────────────────


def test_get_account_with_computed_balance(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash", initial="100000.00")
    _create_transaction(headers, acc["id"], "40000.00", tx_type="expense")
    _create_transaction(headers, acc["id"], "20000.00", tx_type="income")
    got = client.get(f"/api/accounts/{acc['id']}", headers=headers)
    assert got.status_code == 200
    data = got.json()
    assert data["current_balance"] == "80000.00"  # 100000 - 40000 + 20000
    assert data["net_balance"] == "-20000.00"  # 20000 - 40000


def test_update_account(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash")
    resp = client.put(
        f"/api/accounts/{acc['id']}",
        json={"account_name": "Wallet", "account_type": "ewallet"},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["account_name"] == "Wallet"
    assert resp.json()["account_type"] == "ewallet"


def test_inactive_account_not_found_for_get_update(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash")
    client.post(f"/api/accounts/{acc['id']}/deactivate", json={}, headers=headers)
    assert client.get(f"/api/accounts/{acc['id']}", headers=headers).status_code == 404
    resp = client.put(f"/api/accounts/{acc['id']}", json={"account_name": "X"}, headers=headers)
    assert resp.status_code == 404


# ── Deactivate (soft-delete, NEVER hard-delete) ──────────────────────────────


def test_no_delete_endpoint(auth):
    """Accounts can only be deactivated — there is no DELETE route (405)."""
    headers = auth()
    acc = _create_account(headers, name="Cash")
    resp = client.delete(f"/api/accounts/{acc['id']}", headers=headers)
    assert resp.status_code == 405


def test_deactivate_zero_balance(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash")
    resp = client.post(f"/api/accounts/{acc['id']}/deactivate", json={}, headers=headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    # No transfer transactions were created (balance was zero).
    txs = client.get("/api/transactions", headers=headers).json()
    assert txs["items"] == []


def test_deactivate_with_balance_requires_target(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash", initial="50000.00")
    resp = client.post(f"/api/accounts/{acc['id']}/deactivate", json={}, headers=headers)
    assert resp.status_code == 400
    assert "balance" in resp.json()["detail"].lower()


def test_deactivate_moves_balance_to_target(auth):
    headers = auth()
    source = _create_account(headers, name="Cash", initial="50000.00")
    _create_transaction(headers, source["id"], "10000.00", tx_type="expense")
    target = _create_account(headers, name="BCA")
    resp = client.post(
        f"/api/accounts/{source['id']}/deactivate",
        json={"target_account_id": target["id"]},
        headers=headers,
    )
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False
    # The deactivation response recomputes the source balance AFTER the
    # balancing transfer → drained to zero.
    assert resp.json()["current_balance"] == "0.00"

    # Target received the balance via the balancing transfer (type='transfer').
    tgt = client.get(f"/api/accounts/{target['id']}", headers=headers).json()
    assert tgt["current_balance"] == "40000.00"

    # SATU transaksi transfer: saldo keluar dari sumber, masuk ke tujuan.
    # Netral di laporan income/expense, tanpa kategori (migrasi 0008).
    txs = client.get("/api/transactions", headers=headers).json()["items"]
    transfer_txs = [t for t in txs if t["note"] and "Saldo dipindah" in t["note"]]
    assert len(transfer_txs) == 1
    t = transfer_txs[0]
    assert t["type"] == "transfer"
    assert t["category_id"] is None
    assert t["account_id"] == source["id"]
    assert t["to_account_id"] == target["id"]


def test_deactivate_target_must_differ(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash", initial="1000.00")
    resp = client.post(
        f"/api/accounts/{acc['id']}/deactivate",
        json={"target_account_id": acc["id"]},
        headers=headers,
    )
    assert resp.status_code == 400


def test_deactivate_target_not_found(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash", initial="1000.00")
    resp = client.post(
        f"/api/accounts/{acc['id']}/deactivate",
        json={"target_account_id": "00000000-0000-0000-0000-000000000000"},
        headers=headers,
    )
    assert resp.status_code == 404


# ── Inactive accounts excluded from new-transaction input (CODING_RULES §2.8) ─


def test_inactive_account_rejected_for_new_transaction(auth):
    headers = auth()
    acc = _create_account(headers, name="Cash")
    client.post(f"/api/accounts/{acc['id']}/deactivate", json={}, headers=headers)
    cat = client.post(
        "/api/categories", json={"name": "Test", "type": "expense"}, headers=headers
    ).json()
    resp = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "total_amount": "1000.00",
            "category_id": cat["id"],
            "account_id": acc["id"],
        },
        headers=headers,
    )
    assert resp.status_code == 422
