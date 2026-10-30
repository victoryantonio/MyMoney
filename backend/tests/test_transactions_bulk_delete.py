"""
Test untuk `POST /api/transactions/bulk-delete` (hapus massal dari UI multi-pilih).

Berbeda dengan test API lain, di sini autentikasi di-override lewat
`app.dependency_overrides` (`require_active_user` → fixture `profile`), sehingga
test tetap berjalan lokal tanpa kredensial Supabase. Yang dijaga:

  * hanya baris milik user yang dihapus (isolasi antar user)
  * id yang tidak ada / milik user lain dilaporkan di `missing`, bukan error
  * item ikut terhapus (CASCADE)
  * audit log tercatat per baris dengan penanda `bulk`
  * validasi body (list kosong → 422, terlalu banyak → 422)
"""

import uuid
from datetime import UTC, datetime
from decimal import Decimal

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.api.deps import get_db, require_active_user
from app.core.rate_limit import limiter
from app.main import app
from app.models.account import Account
from app.models.audit_log import AuditLog
from app.models.category import Category
from app.models.transaction import Transaction
from app.models.transaction_item import TransactionItem

client = TestClient(app)

_ENDPOINT = "/api/transactions/bulk-delete"


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Endpoint dibatasi 20/menit per IP — reset antar-test."""
    limiter.reset()
    yield
    limiter.reset()


@pytest.fixture
def auth(profile, db):
    """Override auth + db agar endpoint memakai sesi & user test yang sama."""
    app.dependency_overrides[require_active_user] = lambda: profile
    app.dependency_overrides[get_db] = lambda: db
    yield profile
    app.dependency_overrides.clear()


@pytest.fixture
def seeded(db, auth):
    """Dua transaksi (masing-masing 1 item) milik user test."""
    category = Category(
        user_id=auth.id,
        name="Bulk Test",
        type="expense",
        is_default=False,
        is_active=True,
    )
    account = Account(user_id=auth.id, account_name="Cash Bulk", account_type="cash")
    db.add_all([category, account])
    db.commit()

    transactions = []
    for amount in (Decimal("10000"), Decimal("20000")):
        tx = Transaction(
            user_id=auth.id,
            type="expense",
            total_amount=amount,
            category_id=category.id,
            account_id=account.id,
            transaction_date=datetime(2026, 9, 10, 3, 0, tzinfo=UTC),
            source="app",
        )
        db.add(tx)
        db.flush()
        db.add(
            TransactionItem(
                transaction_id=tx.id,
                name="Item",
                qty=Decimal("1"),
                price=amount,
            )
        )
        transactions.append(tx)
    db.commit()
    return transactions


def _delete(headers: dict | None = None, json_body: dict | None = None):
    return client.post(_ENDPOINT, headers=headers, json=json_body)


class TestBulkDelete:
    def test_deletes_selected_transactions_and_items(self, db, seeded):
        ids = [str(tx.id) for tx in seeded]

        resp = _delete(json_body={"ids": ids})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] == 2
        assert body["missing"] == []

        remaining = db.scalars(
            select(Transaction).where(Transaction.id.in_([tx.id for tx in seeded]))
        ).all()
        assert remaining == []
        items = db.scalars(
            select(TransactionItem).where(
                TransactionItem.transaction_id.in_([tx.id for tx in seeded])
            )
        ).all()
        assert items == []

    def test_reports_unknown_and_foreign_ids_as_missing(self, db, seeded):
        mine = seeded[0]
        stranger = uuid.uuid4()

        resp = _delete(json_body={"ids": [str(mine.id), str(stranger)]})

        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["deleted"] == 1
        assert body["missing"] == [str(stranger)]
        # Baris yang tidak diminta tetap ada.
        assert db.get(Transaction, seeded[1].id) is not None

    def test_duplicate_ids_are_deleted_once(self, db, seeded):
        tx_id = str(seeded[0].id)
        resp = _delete(json_body={"ids": [tx_id, tx_id]})

        assert resp.status_code == 200, resp.text
        assert resp.json()["deleted"] == 1
        assert resp.json()["missing"] == []

    def test_audit_log_written_per_row_with_bulk_flag(self, db, seeded):
        ids = [str(tx.id) for tx in seeded]
        assert _delete(json_body={"ids": ids}).status_code == 200

        entries = db.scalars(
            select(AuditLog).where(
                AuditLog.user_id == seeded[0].user_id,
                AuditLog.entity_type == "transaction",
                AuditLog.action == "delete",
            )
        ).all()
        assert len(entries) == 2
        assert all((entry.old_value or {}).get("bulk") is True for entry in entries)

    def test_rejects_empty_list(self, auth):
        assert _delete(json_body={"ids": []}).status_code == 422

    def test_rejects_too_many_ids(self, auth):
        too_many = [str(uuid.uuid4()) for _ in range(201)]
        assert _delete(json_body={"ids": too_many}).status_code == 422

    def test_requires_authentication(self):
        app.dependency_overrides.clear()
        assert _delete(json_body={"ids": [str(uuid.uuid4())]}).status_code == 401
