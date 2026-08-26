"""
Tests for audit trail (CODING_RULES §2.6).

- record_audit() validation (unit, mocked session)
- audit row actually persisted on transaction create (integration, real DB)

Requires a running PostgreSQL (CI provides it via the postgres service container).
"""

import uuid
from decimal import Decimal
from unittest.mock import MagicMock

import pytest
from sqlalchemy import select

from app.core.audit_service import record_audit
from app.core.transaction_service import (
    create_transaction_internal,
    get_or_create_category,
    get_or_create_default_account,
)
from app.models.audit_log import AuditLog

# ── Unit: validation (mocked session) ─────────────────────────────────────────


def test_invalid_action_rejected():
    db = MagicMock()
    with pytest.raises(ValueError, match="invalid audit action"):
        record_audit(db, user_id=uuid.uuid4(), action="explode", entity_type="x", source="app")


def test_invalid_source_rejected():
    db = MagicMock()
    with pytest.raises(ValueError, match="invalid audit source"):
        record_audit(db, user_id=uuid.uuid4(), action="create", entity_type="x", source="web")


def test_valid_entry_added_and_flushed():
    db = MagicMock()
    record_audit(
        db,
        user_id=uuid.uuid4(),
        action="create",
        entity_type="transaction",
        source="app",
        new_value={"total_amount": "1000"},
    )
    db.add.assert_called_once()
    db.flush.assert_called_once()


# ── Integration: audit row persisted (real DB) ────────────────────────────────


def _latest_audit(db, user_id) -> AuditLog | None:
    return db.scalar(
        select(AuditLog)
        .where(AuditLog.user_id == user_id)
        .order_by(AuditLog.created_at.desc())
        .limit(1)
    )


def test_create_transaction_writes_audit_row(db, profile):
    account = get_or_create_default_account(db, profile.id)
    category = get_or_create_category(db, profile.id, "Food", "expense")

    tx = create_transaction_internal(
        db=db,
        user_id=profile.id,
        type="expense",
        total_amount=Decimal("35000"),
        category_id=category.id,
        account_id=account.id,
        source="telegram",
        note="Makan siang",
    )

    row = _latest_audit(db, profile.id)
    assert row is not None
    assert row.action == "create"
    assert row.entity_type == "transaction"
    assert row.entity_id == tx.id
    assert row.source == "telegram"
    assert row.new_value["total_amount"] == "35000"
    assert row.old_value is None
