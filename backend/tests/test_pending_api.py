"""
API tests untuk `/api/pending` — layar "Matching" di app Flutter.

Latar belakang: baris mutasi bank yang BELUM cocok dengan transaksi tercatat
tidak pernah langsung disimpan sebagai transaksi (CODING_RULES §2.4); baris itu
masuk `pending_transactions` menunggu konfirmasi. Sebelum router ini ada, user
mendapat instruksi "buka menu Pending" padahal belum ada endpoint maupun layar
untuk itu.

Yang dijaga test ini:
  * daftar pending hanya memuat baris AKTIF milik user yang login
  * konfirmasi membuat transaksi nyata dan menghapus baris pending
  * pembatalan tidak menyimpan transaksi apa pun
  * pending milik user lain / id tidak dikenal → 404 (bukan 500)
  * pending kedaluwarsa & pending yang tergantikan unggahan baru dibersihkan
    dari tabel (housekeeping)
"""

import uuid
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.mutation_matcher import MutationExtraction, ParsedMutation
from app.main import app

client = TestClient(app)

_MATCH_ENDPOINT = "/api/mutations/match"
_PENDING_ENDPOINT = "/api/pending"


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per call → Bearer headers (skip di CI tanpa creds)."""
    return supabase_factory


def _create_account(headers, name="BCA Matching"):
    resp = client.post(
        "/api/accounts",
        json={"account_name": name, "initial_balance": "0.00", "account_type": "bank"},
        headers=headers,
    )
    assert resp.status_code == 201, resp.text
    return resp.json()


def _seed_pending(
    headers,
    *,
    amount="135000",
    description="QRIS TOKO ABC",
    date="2026-08-02",
    direction="debit",
    account_id=None,
):
    """Unggah satu baris mutasi (parser di-mock) → satu pending. Kembalikan id-nya."""
    extraction = MutationExtraction(
        account_hint=None,
        mutations=[
            ParsedMutation(
                date=date,
                time=None,
                description=description,
                amount=amount,
                direction=direction,
            )
        ],
    )
    with patch("app.api.mutations.parse_mutation_text", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = extraction
        resp = client.post(
            _MATCH_ENDPOINT,
            files={"file": ("mutasi.csv", b"a,b,c", "text/csv")},
            data={"account_id": account_id} if account_id else None,
            headers=headers,
        )
    assert resp.status_code == 200, resp.text
    pending_ids = resp.json()["created_pending_ids"]
    assert len(pending_ids) == 1, resp.text
    return pending_ids[0]


def _list_pending(headers):
    resp = client.get(_PENDING_ENDPOINT, headers=headers)
    assert resp.status_code == 200, resp.text
    return resp.json()


def _transaction_amounts(headers):
    resp = client.get("/api/transactions", headers=headers)
    assert resp.status_code == 200, resp.text
    payload = resp.json()
    rows = payload["items"] if isinstance(payload, dict) else payload
    return [row["total_amount"] for row in rows]


# ── Auth ─────────────────────────────────────────────────────────────────────


def test_list_requires_auth():
    """Tanpa JWT → 401 (tidak ada kebocoran data pending siapa pun)."""
    assert client.get(_PENDING_ENDPOINT).status_code == 401


def test_confirm_requires_auth():
    assert (
        client.post(f"{_PENDING_ENDPOINT}/00000000-0000-0000-0000-000000000000/confirm").status_code
        == 401
    )


def test_cancel_requires_auth():
    assert (
        client.post(f"{_PENDING_ENDPOINT}/00000000-0000-0000-0000-000000000000/cancel").status_code
        == 401
    )


# ── Daftar pending ───────────────────────────────────────────────────────────


def test_empty_list_for_new_user(auth):
    body = _list_pending(auth("pending_empty"))
    assert body == {"items": [], "total": 0}


def test_unmatched_mutation_appears_in_list(auth):
    """Baris mutasi yang belum tercatat harus bisa dilihat dari /api/pending."""
    headers = auth("pending_list")
    account = _create_account(headers)
    _seed_pending(
        headers,
        amount="135000",
        description="QRIS TOKO ABC",
        account_id=account["id"],
    )

    body = _list_pending(headers)
    assert body["total"] == 1
    row = body["items"][0]
    assert row["type"] == "expense"
    assert row["action"] == "create"
    assert row["total_amount"] == "135000.00"
    assert row["merchant"] == "QRIS TOKO ABC"
    assert row["account_id"] == account["id"]
    assert row["account_name"] == "BCA Matching"
    assert row["category_id"]
    assert row["category_name"]
    assert row["raw_input"].startswith("Matching Mutasi")
    assert row["expires_at"] is not None


def test_credit_mutation_maps_to_income(auth):
    """Mutasi masuk (credit) → pending bertipe income."""
    headers = auth("pending_income")
    _seed_pending(
        headers,
        amount="500000",
        description="TRANSFER MASUK",
        direction="credit",
    )

    body = _list_pending(headers)
    assert body["items"][0]["type"] == "income"


def test_count_endpoint(auth):
    headers = auth("pending_count")
    assert client.get(f"{_PENDING_ENDPOINT}/count", headers=headers).json() == {"count": 0}

    _seed_pending(headers, amount="15000", description="KOPI KENANGAN")
    assert client.get(f"{_PENDING_ENDPOINT}/count", headers=headers).json() == {"count": 1}


def test_pending_isolation_between_users(auth):
    """Pending user A tidak boleh terlihat (atau bisa dikonfirmasi) oleh user B."""
    headers_a = auth("pending_owner")
    headers_b = auth("pending_other")
    pending_id = _seed_pending(headers_a, amount="777000", description="RAHASIA A")

    assert _list_pending(headers_b)["total"] == 0
    resp = client.post(f"{_PENDING_ENDPOINT}/{pending_id}/confirm", headers=headers_b)
    assert resp.status_code == 404, resp.text


# ── Konfirmasi ───────────────────────────────────────────────────────────────


def test_confirm_creates_transaction_and_clears_pending(auth):
    headers = auth("pending_confirm")
    account = _create_account(headers, name="Mandiri")
    pending_id = _seed_pending(
        headers,
        amount="987654",
        description="QRIS TOKO ABC",
        account_id=account["id"],
    )

    resp = client.post(f"{_PENDING_ENDPOINT}/{pending_id}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["pending_id"] == pending_id
    assert body["type"] == "expense"
    assert body["total_amount"] == "987654.00"
    assert body["transaction_id"]

    # Pending hilang, transaksi nyata muncul.
    assert _list_pending(headers)["total"] == 0
    assert "987654.00" in _transaction_amounts(headers)


def test_confirm_is_idempotent_after_first_call(auth):
    """Konfirmasi kedua untuk id yang sama → 404, bukan transaksi ganda."""
    headers = auth("pending_double")
    pending_id = _seed_pending(headers, amount="42000", description="INDOMARET")

    assert (
        client.post(f"{_PENDING_ENDPOINT}/{pending_id}/confirm", headers=headers).status_code == 200
    )
    again = client.post(f"{_PENDING_ENDPOINT}/{pending_id}/confirm", headers=headers)
    assert again.status_code == 404
    assert _transaction_amounts(headers).count("42000.00") == 1


def test_confirm_unknown_id_returns_404(auth):
    resp = client.post(
        f"{_PENDING_ENDPOINT}/11111111-1111-1111-1111-111111111111/confirm",
        headers=auth("pending_unknown"),
    )
    assert resp.status_code == 404
    assert "tidak ditemukan" in resp.json()["detail"]


# ── Pembatalan ───────────────────────────────────────────────────────────────


def test_cancel_discards_pending_without_transaction(auth):
    headers = auth("pending_cancel")
    pending_id = _seed_pending(headers, amount="123321", description="TOKO BANGUNAN")

    resp = client.post(f"{_PENDING_ENDPOINT}/{pending_id}/cancel", headers=headers)
    assert resp.status_code == 200, resp.text
    assert resp.json()["cancelled"] is True

    assert _list_pending(headers)["total"] == 0
    assert "123321.00" not in _transaction_amounts(headers)


def _cancel_unknown_id_returns_404(auth):
    resp = client.post(
        f"{_PENDING_ENDPOINT}/22222222-2222-2222-2222-222222222222/cancel",
        headers=auth("pending_cancel_unknown"),
    )
    assert resp.status_code == 404


# ── Housekeeping (tabel pending tidak boleh menumpuk baris mati) ──────────────


def _expire_pending(pending_id: str) -> None:
    """Paksa satu pending kedaluwarsa langsung di DB (tanpa menunggu 24 jam)."""
    from datetime import UTC, datetime, timedelta

    from app.db.session import SessionLocal
    from app.models.pending_transaction import PendingTransaction

    with SessionLocal() as session:
        row = session.get(PendingTransaction, uuid.UUID(pending_id))
        assert row is not None
        row.expires_at = datetime.now(UTC) - timedelta(minutes=1)
        session.commit()


def _pending_row_exists(pending_id: str) -> bool:
    from app.db.session import SessionLocal
    from app.models.pending_transaction import PendingTransaction

    with SessionLocal() as session:
        return session.get(PendingTransaction, uuid.UUID(pending_id)) is not None


def test_expired_pending_is_purged_on_list(auth):
    """Pending yang tidak pernah dikonfirmasi & kedaluwarsa → dihapus dari tabel."""
    headers = auth("pending_expire")
    pending_id = _seed_pending(headers, amount="31000", description="PARKIR")
    assert _pending_row_exists(pending_id)

    _expire_pending(pending_id)

    assert _list_pending(headers)["total"] == 0
    assert not _pending_row_exists(pending_id)


def test_expired_pending_is_purged_on_count(auth):
    headers = auth("pending_expire_count")
    pending_id = _seed_pending(headers, amount="32000", description="AIR MINERAL")
    _expire_pending(pending_id)

    assert client.get(f"{_PENDING_ENDPOINT}/count", headers=headers).json() == {"count": 0}
    assert not _pending_row_exists(pending_id)


def test_expired_pending_cannot_be_confirmed(auth):
    """Pending kedaluwarsa tidak bisa dikonfirmasi (410) dan ikut dibersihkan."""
    headers = auth("pending_expire_confirm")
    pending_id = _seed_pending(headers, amount="33000", description="BAKSO")
    _expire_pending(pending_id)

    resp = client.post(f"{_PENDING_ENDPOINT}/{pending_id}/confirm", headers=headers)
    assert resp.status_code == 410, resp.text
    assert not _pending_row_exists(pending_id)
    assert "33000.00" not in _transaction_amounts(headers)


def test_new_upload_replaces_previous_pendings(auth):
    """Unggah ulang mutasi → pending lama yang belum dikonfirmasi dibuang."""
    headers = auth("pending_replace")
    old_id = _seed_pending(headers, amount="111000", description="MUTASI LAMA")
    new_id = _seed_pending(headers, amount="222000", description="MUTASI BARU")

    body = _list_pending(headers)
    assert body["total"] == 1
    assert body["items"][0]["id"] == new_id
    assert body["items"][0]["merchant"] == "MUTASI BARU"
    assert not _pending_row_exists(old_id)


def test_failed_upload_keeps_existing_pending(auth):
    """Berkas gagal dibaca tidak boleh menghapus pending yang masih berlaku."""
    headers = auth("pending_keep")
    pending_id = _seed_pending(headers, amount="444000", description="SIMPAN")

    bad = client.post(
        _MATCH_ENDPOINT,
        files={"file": ("mutasi.csv", b"", "text/csv")},
        headers=headers,
    )
    assert bad.status_code == 422
    assert _pending_row_exists(pending_id)
    assert _list_pending(headers)["total"] == 1


def test_confirmed_rows_are_not_affected_by_purge(auth):
    """Yang sudah dikonfirmasi jadi transaksi nyata — tidak ikut terhapus."""
    headers = auth("pending_confirmed_keep")
    confirmed_id = _seed_pending(headers, amount="555000", description="SUDAH OK")
    resp = client.post(f"{_PENDING_ENDPOINT}/{confirmed_id}/confirm", headers=headers)
    assert resp.status_code == 200, resp.text

    # Unggah baru memicu purge pending lama — transaksi hasil konfirmasi tetap ada.
    _seed_pending(headers, amount="666000", description="BARU LAGI")
    assert "555000.00" in _transaction_amounts(headers)
    assert _list_pending(headers)["total"] == 1
