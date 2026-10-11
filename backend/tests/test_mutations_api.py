"""
API tests untuk fitur "Matching Mutasi" (Req 9) — `POST /api/mutations/match`.

Vision/text LLM di-mock (`parse_mutation_text`), jadi test ini hanya menguji
kontrak endpoint + logika pencocokan terhadap PostgreSQL nyata. Butuh Postgres
+ Supabase creds (sama seperti test API lain; skip di CI tanpa creds).

Yang dijaga:
  * auth & validasi input (401 / 422 / 415) sebelum LLM dipanggil
  * mutasi yang SUDAH tercatat → matched, tidak ada pending
  * mutasi yang BELUM tercatat → `pending_transaction`, bukan transaksi nyata
    (CODING_RULES §2.4)
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.mutation_matcher import MutationExtraction, ParsedMutation
from app.core.rate_limit import limiter
from app.main import app

client = TestClient(app)

_ENDPOINT = "/api/mutations/match"


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skip di CI tanpa creds)."""
    return supabase_factory


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Endpoint ini dibatasi 10/menit per IP — reset antar-test."""
    limiter.reset()
    yield
    limiter.reset()


def _upload(headers=None, content=b"date,description,amount\n", filename="mutasi.csv"):
    return client.post(
        _ENDPOINT,
        files={"file": (filename, content, "text/csv")},
        headers=headers,
    )


def _extraction(*mutations) -> MutationExtraction:
    return MutationExtraction(account_hint=None, mutations=list(mutations))


def _debit(amount, date=None, description="TRANSFER KE 1234"):
    return ParsedMutation(
        date=date,
        time=None,
        description=description,
        amount=amount,
        direction="debit",
    )


def _create_account(headers, name="BCA Tahunan"):
    resp = client.post(
        "/api/accounts",
        json={"account_name": name, "initial_balance": "0.00", "account_type": "bank"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _create_transaction(headers, account_id, amount, tx_date, cat_name="Mutasi Test"):
    cat = client.post(
        "/api/categories", json={"name": cat_name, "type": "expense"}, headers=headers
    )
    assert cat.status_code == 201, cat.text
    resp = client.post(
        "/api/transactions",
        json={
            "type": "expense",
            "total_amount": amount,
            "category_id": cat.json()["id"],
            "account_id": account_id,
            "merchant": "Mixue",
            "transaction_date": tx_date,
        },
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


# ── Auth & validasi input ────────────────────────────────────────────────────


def test_requires_auth():
    """Tanpa JWT → 401 dan LLM tidak boleh dipanggil."""
    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        resp = _upload()
        assert resp.status_code == 401
        mock_parse.assert_not_awaited()


def test_empty_file_rejected(auth):
    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        resp = _upload(auth("mut_empty"), content=b"")
        assert resp.status_code == 422
        mock_parse.assert_not_awaited()


def test_unsupported_media_type_rejected(auth):
    """File non-gambar non-CSV → 415 sebelum LLM dipanggil."""
    with patch("app.api.mutations.parse_mutation_image", new_callable=AsyncMock) as mock_parse:
        resp = client.post(
            _ENDPOINT,
            files={"file": ("mutasi.pdf", b"%PDF-1.4", "application/pdf")},
            headers=auth("mut_pdf"),
        )
        assert resp.status_code == 415
        mock_parse.assert_not_awaited()


def test_unreadable_statement_returns_422(auth):
    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = None
        resp = _upload(auth("mut_unread"))
        assert resp.status_code == 422
        assert "tidak terbaca" in resp.json()["detail"]


def test_invalid_tolerance_rejected(auth):
    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        resp = client.post(
            _ENDPOINT,
            files={"file": ("mutasi.csv", b"a,b,c", "text/csv")},
            data={"amount_tolerance": "banyak"},
            headers=auth("mut_tol"),
        )
        assert resp.status_code == 422
        mock_parse.assert_not_awaited()


# ── Pencocokan ───────────────────────────────────────────────────────────────


def test_recorded_transaction_is_matched(auth):
    """Mutasi yang sudah tercatat → matched, tanpa pending baru."""
    headers = auth("mut_match")
    account = _create_account(headers)
    _create_transaction(headers, account["id"], "21000.00", tx_date="2026-08-01T10:00:00Z")

    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = _extraction(_debit("21000", date="2026-08-01"))
        resp = client.post(
            _ENDPOINT,
            files={"file": ("mutasi.csv", b"a,b,c", "text/csv")},
            data={"account_id": account["id"]},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["total_mutations"] == 1
    assert data["matched_count"] == 1
    assert data["unmatched_mutation_count"] == 0
    assert data["created_pending_ids"] == []
    assert data["account_id"] == account["id"]
    assert data["account_name"] == "BCA Tahunan"
    assert data["matches"][0]["transaction_type"] == "expense"
    assert data["matches"][0]["amount_diff"] == "0.00"


def test_unrecorded_mutation_creates_pending_not_transaction(auth):
    """Mutasi yang belum tercatat → pending_transaction (CODING_RULES §2.4)."""
    headers = auth("mut_pending")
    account = _create_account(headers, name="Mandiri")

    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = _extraction(
            _debit("987654", date="2026-08-02", description="QRIS TOKO ABC")
        )
        resp = client.post(
            _ENDPOINT,
            files={"file": ("mutasi.csv", b"a,b,c", "text/csv")},
            data={"account_id": account["id"]},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    data = resp.json()
    assert data["matched_count"] == 0
    assert data["unmatched_mutation_count"] == 1
    assert len(data["created_pending_ids"]) == 1
    assert data["unmatched_mutations"][0]["description"] == "QRIS TOKO ABC"

    # Transaksi nyata TIDAK boleh ikut terbuat — hanya pending.
    listed = client.get("/api/transactions", headers=headers)
    assert listed.status_code == 200
    payload = listed.json()
    rows = payload["items"] if isinstance(payload, dict) else payload
    assert all(row["total_amount"] != "987654.00" for row in rows)


def test_tolerance_and_window_are_clamped(auth):
    """date_window_days ekstrem tidak boleh melampaui batas 30 hari."""
    headers = auth("mut_clamp")

    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = _extraction(_debit("111111", date="2026-08-03"))
        resp = client.post(
            _ENDPOINT,
            files={"file": ("mutasi.csv", b"a,b,c", "text/csv")},
            data={"amount_tolerance": "2.50", "date_window_days": "999"},
            headers=headers,
        )

    assert resp.status_code == 200, resp.text
    assert resp.json()["unmatched_mutation_count"] == 1
