"""
Unit tests for pending_service.py — the pending-confirmation gate for LLM
parse results (CODING_RULES §2.4, REQUIREMENTS US-05/US-08).

Uses a mocked Session (like test_telegram_service.py) — no DB required.
"""

import uuid
from datetime import UTC, datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.pending_service import (
    cancel_pending_transaction,
    confirm_pending_transaction,
    create_pending_transaction,
    get_latest_active_pending,
)
from app.models.pending_transaction import PendingTransaction
from app.models.transaction import Transaction


def _pending(**overrides) -> PendingTransaction:
    """Build a PendingTransaction with sane defaults."""
    defaults = dict(
        id=uuid.uuid4(),
        user_id=uuid.uuid4(),
        action="create",
        type="expense",
        total_amount=Decimal("35000"),
        category_id=uuid.uuid4(),
        source="telegram",
        note="Makan siang",
        raw_input="Makan siang 35rb",
        expires_at=datetime.now(UTC) + timedelta(minutes=10),
    )
    defaults.update(overrides)
    return PendingTransaction(**defaults)


class TestCreatePending:
    def test_creates_and_commits_with_expiry(self):
        db = MagicMock(spec=Session)
        pending = create_pending_transaction(
            db,
            user_id=uuid.uuid4(),
            type="expense",
            total_amount=Decimal("5000"),
            category_id=uuid.uuid4(),
            source="telegram",
            raw_input="Kopi 5k",
        )
        db.add.assert_called_once()
        db.commit.assert_called_once()
        db.refresh.assert_called_once()
        assert pending.action == "create"
        assert pending.expires_at is not None
        assert pending.expires_at > datetime.now(UTC)

    def test_update_action_requires_target(self):
        db = MagicMock(spec=Session)
        with pytest.raises(ValueError, match="requires target_transaction_id"):
            create_pending_transaction(
                db,
                user_id=uuid.uuid4(),
                type="expense",
                total_amount=Decimal("5000"),
                category_id=uuid.uuid4(),
                source="telegram",
                action="update",
            )


class TestConfirm:
    def test_confirm_create_delegates_and_keeps_pending(self):
        db = MagicMock(spec=Session)
        pending = _pending()
        db.scalar.return_value = pending
        account = MagicMock()
        account.id = uuid.uuid4()
        tx = MagicMock(spec=Transaction)

        with (
            patch(
                "app.core.pending_service.get_or_create_default_account", return_value=account
            ) as mock_account,
            patch(
                "app.core.pending_service.create_transaction_internal", return_value=tx
            ) as mock_create,
        ):
            result = confirm_pending_transaction(db, pending.user_id, pending.id)

        assert result is tx
        mock_account.assert_called_once_with(db, pending.user_id)
        call_args = mock_create.call_args
        assert call_args.kwargs["pending"] is pending
        assert call_args.kwargs["user_id"] == pending.user_id
        assert call_args.kwargs["total_amount"] == pending.total_amount
        assert call_args.kwargs["source"] == "telegram"

    def test_confirm_update_delegates_to_update_internal(self):
        db = MagicMock(spec=Session)
        target = MagicMock(spec=Transaction)
        db.get.return_value = target
        pending = _pending(action="update", target_transaction_id=target.id)
        db.scalar.return_value = pending
        tx = MagicMock(spec=Transaction)

        with patch(
            "app.core.pending_service.update_transaction_internal", return_value=tx
        ) as mock_update:
            result = confirm_pending_transaction(db, pending.user_id, pending.id)

        assert result is tx
        db.get.assert_called_once_with(Transaction, target.id)
        call_args = mock_update.call_args
        assert call_args.kwargs["transaction"] is target
        assert call_args.kwargs["pending"] is pending

    def test_confirm_update_target_missing_raises(self):
        db = MagicMock(spec=Session)
        db.get.return_value = None
        pending = _pending(action="update", target_transaction_id=uuid.uuid4())
        db.scalar.return_value = pending

        with pytest.raises(ValueError, match="no longer exists"):
            confirm_pending_transaction(db, pending.user_id, pending.id)
        db.delete.assert_called_once_with(pending)
        db.commit.assert_called_once()

    def test_confirm_expired_purges_and_raises(self):
        db = MagicMock(spec=Session)
        pending = _pending(expires_at=datetime.now(UTC) - timedelta(minutes=1))
        db.scalar.return_value = pending

        with pytest.raises(ValueError, match="expired"):
            confirm_pending_transaction(db, pending.user_id, pending.id)
        db.delete.assert_called_once_with(pending)
        db.commit.assert_called_once()

    def test_confirm_no_pending_raises(self):
        db = MagicMock(spec=Session)
        db.scalar.return_value = None

        with pytest.raises(ValueError, match="no pending"):
            confirm_pending_transaction(db, uuid.uuid4())


class TestCancel:
    def test_cancel_deletes_pending(self):
        db = MagicMock(spec=Session)
        pending = _pending()
        db.scalar.return_value = pending

        result = cancel_pending_transaction(db, pending.user_id)

        assert result is pending
        db.delete.assert_called_once_with(pending)
        db.commit.assert_called_once()

    def test_cancel_no_pending_raises(self):
        db = MagicMock(spec=Session)
        db.scalar.return_value = None

        with pytest.raises(ValueError, match="no pending"):
            cancel_pending_transaction(db, uuid.uuid4())


class TestGetLatest:
    def test_returns_active_pending(self):
        db = MagicMock(spec=Session)
        pending = _pending()
        db.scalar.return_value = pending

        assert get_latest_active_pending(db, pending.user_id) is pending

    def test_returns_none_when_none(self):
        db = MagicMock(spec=Session)
        db.scalar.return_value = None

        assert get_latest_active_pending(db, uuid.uuid4()) is None
