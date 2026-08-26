"""
Unit tests for telegram_service.py — testing /start, /logout, /undo, /edit,
/confirm, /cancel, /report, and text parsing.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.telegram_service import process_telegram_update
from app.models.account import Account
from app.models.category import Category
from app.models.profile import Profile
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction


class TestProcessTelegramUpdate:
    """Tests for the process_telegram_update function."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db = MagicMock(spec=Session)
        self.user_id = uuid.uuid4()
        self.telegram_id = 123456789
        self.chat_id = 123456789

    def _make_update(self, text: str) -> dict:
        """Create a mock Telegram update dict."""
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "chat": {"id": self.chat_id, "type": "private"},
                "from": {"id": self.telegram_id, "is_bot": False, "first_name": "Test"},
                "text": text,
            },
        }

    # ── /start tests ──────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_start_not_linked_returns_link_url(self):
        """Test /start returns linking URL when user not linked."""
        # No existing link
        self.db.scalar.return_value = None

        with patch("app.core.telegram_service.create_telegram_link_token") as mock_token:
            mock_token.return_value = "test-token"
            with patch("app.core.telegram_service.settings.app_base_url", "https://example.com"):
                result = await process_telegram_update(self.db, self._make_update("/start"))

        assert "Welcome to MyMoney" in result
        assert "https://example.com/api/telegram/link?token=test-token" in result
        assert "expires in 10 minutes" in result

    @pytest.mark.asyncio
    async def test_start_already_linked_returns_welcome(self):
        """Test /start returns welcome message when already linked."""
        # Existing link
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        user = Profile(
            id=self.user_id,
            display_name="Test User",
        )
        self.db.scalar.return_value = link
        self.db.get.return_value = user

        result = await process_telegram_update(self.db, self._make_update("/start"))

        assert "Welcome back, Test User" in result
        assert "already linked" in result

    @pytest.mark.asyncio
    async def test_start_link_exists_but_no_user(self):
        """Test /start when link exists but user not found (edge case)."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link
        self.db.get.return_value = None  # User deleted

        with patch("app.core.telegram_service.create_telegram_link_token") as mock_token:
            mock_token.return_value = "test-token"
            with patch("app.core.telegram_service.settings.app_base_url", "https://example.com"):
                result = await process_telegram_update(self.db, self._make_update("/start"))

        assert "Welcome to MyMoney" in result

    # ── /logout tests ─────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_logout_success(self):
        """Test /logout unlinks the Telegram account."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("/logout"))

        assert "Logged out" in result
        assert "no longer linked" in result
        self.db.delete.assert_called_once_with(link)
        self.db.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_logout_not_linked(self):
        """Test /logout when not linked returns an error."""
        self.db.scalar.return_value = None

        result = await process_telegram_update(self.db, self._make_update("/logout"))

        assert "not linked yet" in result

    # ── /undo tests ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_undo_no_transactions(self):
        """Test /undo when no transactions exist."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link
        # Second scalar call for finding transaction returns None
        self.db.scalar.side_effect = [link, None]

        result = await process_telegram_update(self.db, self._make_update("/undo"))

        assert "No recent Telegram transaction found to undo" in result

    @pytest.mark.asyncio
    async def test_undo_deletes_transaction(self):
        """Test /undo deletes the most recent transaction."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            source="telegram",
            note="Makan siang",
        )
        self.db.scalar.side_effect = [link, tx]

        result = await process_telegram_update(self.db, self._make_update("/undo"))

        assert "Undid your last transaction" in result
        assert "35,000" in result
        assert "Makan siang" in result
        self.db.delete.assert_called_once_with(tx)
        self.db.commit.assert_called_once()

    # ── /edit tests ───────────────────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_edit_no_args_returns_usage(self):
        """Test /edit without arguments returns usage message."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("/edit"))

        assert "Usage: /edit" in result
        assert "Example:" in result

    @pytest.mark.asyncio
    async def test_edit_empty_args_returns_error(self):
        """Test /edit with only whitespace collapses to /edit → usage message."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("/edit   "))

        assert "Usage: /edit" in result

    @pytest.mark.asyncio
    async def test_edit_no_transactions(self):
        """Test /edit when no transactions exist."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.side_effect = [link, None]

        result = await process_telegram_update(self.db, self._make_update("/edit makan 50rb"))

        assert "No recent Telegram transaction found to edit" in result

    @pytest.mark.asyncio
    async def test_edit_parsing_fails(self):
        """Test /edit when new text parsing fails."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            source="telegram",
        )
        self.db.scalar.side_effect = [link, tx]

        with patch(
            "app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = None

            result = await process_telegram_update(self.db, self._make_update("/edit hello world"))

        assert "couldn't understand the new transaction" in result

    @pytest.mark.asyncio
    async def test_edit_success(self):
        """Test successful /edit applies the change DIRECTLY (no /confirm gate)."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        old_tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=uuid.uuid4(),
            account_id=uuid.uuid4(),
            source="telegram",
            note="Old note",
        )
        new_category = Category(id=uuid.uuid4(), name="Transport", type="expense")
        updated_tx = Transaction(
            id=old_tx.id,
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("50000"),
            category_id=new_category.id,
            account_id=old_tx.account_id,
            source="telegram",
            note="Bensin",
        )
        self.db.scalar.side_effect = [link, old_tx, new_category]

        with patch(
            "app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock
        ) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction

            mock_parse.return_value = ParsedTransaction(
                type="expense", amount=Decimal("50000"), category="Transport", note="Bensin"
            )
            with patch("app.core.telegram_service.update_transaction_internal") as mock_update:
                mock_update.return_value = updated_tx

                result = await process_telegram_update(
                    self.db, self._make_update("/edit bensin 50rb")
                )

        assert "Edited!" in result
        assert "50,000" in result
        assert "Transport" in result
        assert "Bensin" in result
        assert "/confirm" not in result
        # The edit is applied directly to the latest Telegram transaction.
        mock_update.assert_called_once()
        call_args = mock_update.call_args
        assert call_args.kwargs["transaction"].id == old_tx.id
        assert call_args.kwargs["total_amount"] == Decimal("50000")
        assert call_args.kwargs["note"] == "Bensin"

    # ── /report tests (US-17) ─────────────────────────────────────────────────

    def _report_summary(self, **overrides):
        """Build a ReportSummaryResponse with sensible defaults."""
        from datetime import UTC, datetime

        from app.schemas.report import CategoryTotal, ReportSummaryResponse

        defaults = dict(
            start_date=datetime(2026, 8, 1, tzinfo=UTC),
            end_date=datetime(2026, 9, 1, tzinfo=UTC),
            total_income=Decimal("1000000"),
            total_expense=Decimal("105000"),
            net=Decimal("895000"),
            categories=[
                CategoryTotal(name="Salary", type="income", total=Decimal("1000000")),
                CategoryTotal(name="Food", type="expense", total=Decimal("75000")),
            ],
        )
        defaults.update(overrides)
        return ReportSummaryResponse(**defaults)

    @pytest.mark.asyncio
    async def test_report_requires_link(self):
        """Test /report when user not linked."""
        self.db.scalar.return_value = None

        result = await process_telegram_update(self.db, self._make_update("/report"))

        assert "not linked yet" in result

    @pytest.mark.asyncio
    async def test_report_no_period_arg_defaults_this_month(self):
        """Test /report without an arg parses an empty period (default month)."""

        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link
        self.db.get.return_value = None  # no user row → tz falls back to UTC

        with patch("app.core.telegram_service.get_report_summary") as mock_summary:
            mock_summary.return_value = self._report_summary()

            result = await process_telegram_update(self.db, self._make_update("/report"))

        assert "📊 Report — this month" in result
        assert "📈 Income: 1,000,000 IDR" in result
        assert "📉 Expense: 105,000 IDR" in result
        assert "Net: +895,000 IDR" in result
        assert "Salary" in result
        assert "Food" in result
        # parse_period_arg was called with the empty arg → default boundaries
        assert (
            mock_summary.call_args.kwargs["start_date"] < mock_summary.call_args.kwargs["end_date"]
        )

    @pytest.mark.asyncio
    async def test_report_with_period_arg(self):
        """Test /report minggu-ini passes the period keyword to parse_period_arg."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link
        self.db.get.return_value = None

        with patch("app.core.telegram_service.get_report_summary") as mock_summary:
            mock_summary.return_value = self._report_summary(
                total_income=Decimal("0"),
                total_expense=Decimal("0"),
                net=Decimal("0"),
                categories=[],
            )

            result = await process_telegram_update(self.db, self._make_update("/report minggu ini"))

        assert "📊 Report — this week" in result
        assert "Net: +0 IDR" in result
        assert "No transactions in this period." in result

    @pytest.mark.asyncio
    async def test_report_uses_user_timezone(self):
        """Test /report resolves the user's timezone from the DB row."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        user = Profile(
            id=self.user_id,
            display_name="TZ",
            timezone="Asia/Jakarta",
        )
        self.db.scalar.return_value = link
        self.db.get.return_value = user

        with patch("app.core.telegram_service.get_report_summary") as mock_summary:
            mock_summary.return_value = self._report_summary()

            result = await process_telegram_update(self.db, self._make_update("/report"))

        self.db.get.assert_called_once_with(Profile, self.user_id)
        assert "📊 Report — this month" in result

    # ── Natural language transaction tests ────────────────────────────────────

    @pytest.mark.asyncio
    async def test_text_not_linked_returns_error(self):
        """Test text message when not linked returns error."""
        self.db.scalar.return_value = None

        result = await process_telegram_update(self.db, self._make_update("Makan 35rb"))

        assert "not linked yet" in result

    @pytest.mark.asyncio
    async def test_text_parsing_fails(self):
        """Test text message when parsing fails."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with patch(
            "app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock
        ) as mock_parse:
            mock_parse.return_value = None

            result = await process_telegram_update(self.db, self._make_update("Hello world"))

        assert "couldn't understand that transaction" in result

    @pytest.mark.asyncio
    async def test_text_parsing_success(self):
        """Test successful text parsing commits a transaction DIRECTLY (no /confirm)."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        category = Category(id=uuid.uuid4(), name="Food", type="expense")
        account = Account(id=uuid.uuid4(), user_id=self.user_id, account_name="Cash")
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=category.id,
            account_id=account.id,
            source="telegram",
            note="Makan siang",
        )
        self.db.scalar.side_effect = [link, category, account]

        with patch(
            "app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock
        ) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction

            mock_parse.return_value = ParsedTransaction(
                type="expense", amount=Decimal("35000"), category="Food", note="Makan siang"
            )
            with patch("app.core.telegram_service.create_transaction_internal") as mock_create:
                mock_create.return_value = tx

                result = await process_telegram_update(
                    self.db, self._make_update("Makan siang 35rb")
                )

        assert "Saved!" in result
        assert "35,000" in result
        assert "Food" in result
        assert "Makan siang" in result
        assert "/confirm" not in result
        # The transaction is committed immediately with source="telegram".
        mock_create.assert_called_once()
        call_args = mock_create.call_args
        assert call_args.kwargs["source"] == "telegram"
        assert call_args.kwargs["note"] == "Makan siang"
        assert call_args.kwargs["account_id"] == account.id
        assert call_args.kwargs["category_id"] == category.id

    @pytest.mark.asyncio
    async def test_text_uses_original_text_as_note_when_none(self):
        """Test that original text is used as note when LLM doesn't provide one."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        category = Category(id=uuid.uuid4(), name="Food", type="expense")
        account = Account(id=uuid.uuid4(), user_id=self.user_id, account_name="Cash")
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=category.id,
            account_id=account.id,
            source="telegram",
            note="Makan siang 35rb",  # original text used as note
        )
        self.db.scalar.side_effect = [link, category, account]

        with patch(
            "app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock
        ) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction

            mock_parse.return_value = ParsedTransaction(
                type="expense",
                amount=Decimal("35000"),
                category="Food",
                note=None,  # LLM didn't provide note
            )
            with patch("app.core.telegram_service.create_transaction_internal") as mock_create:
                mock_create.return_value = tx

                result = await process_telegram_update(
                    self.db, self._make_update("Makan siang 35rb")
                )

        assert "Makan siang 35rb" in result
        # Verify create_transaction_internal was called with original text as note
        call_args = mock_create.call_args
        assert call_args.kwargs["note"] == "Makan siang 35rb"

    # ── /confirm & /cancel tests ─────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_confirm_success(self):
        """Test /confirm persists the pending transaction as a real Transaction."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        category = Category(id=uuid.uuid4(), name="Food", type="expense")
        tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=category.id,
            account_id=uuid.uuid4(),
            source="telegram",
            note="Makan siang",
            category=category,
        )
        self.db.scalar.side_effect = [link, category]

        with patch("app.core.telegram_service.confirm_pending_transaction") as mock_confirm:
            mock_confirm.return_value = tx

            result = await process_telegram_update(self.db, self._make_update("/confirm"))

        assert "Saved!" in result
        assert "35,000" in result
        assert "Food" in result
        mock_confirm.assert_called_once()

    @pytest.mark.asyncio
    async def test_confirm_no_pending(self):
        """Test /confirm with nothing waiting → friendly message."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with patch("app.core.telegram_service.confirm_pending_transaction") as mock_confirm:
            mock_confirm.side_effect = ValueError("no pending transaction found")

            result = await process_telegram_update(self.db, self._make_update("/confirm"))

        assert "No transaction is waiting for confirmation" in result

    @pytest.mark.asyncio
    async def test_confirm_expired(self):
        """Test /confirm with an expired pending → expiry message."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with patch("app.core.telegram_service.confirm_pending_transaction") as mock_confirm:
            mock_confirm.side_effect = ValueError("pending transaction expired")

            result = await process_telegram_update(self.db, self._make_update("/confirm"))

        assert "has expired" in result

    @pytest.mark.asyncio
    async def test_cancel_success(self):
        """Test /cancel discards the pending transaction."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with patch("app.core.telegram_service.cancel_pending_transaction") as mock_cancel:
            mock_cancel.return_value = MagicMock()

            result = await process_telegram_update(self.db, self._make_update("/cancel"))

        assert "Cancelled. Nothing was saved." in result
        mock_cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_cancel_no_pending(self):
        """Test /cancel with nothing waiting → friendly message."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with patch("app.core.telegram_service.cancel_pending_transaction") as mock_cancel:
            mock_cancel.side_effect = ValueError("no pending transaction found")

            result = await process_telegram_update(self.db, self._make_update("/cancel"))

        assert "No transaction is waiting for confirmation" in result

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self):
        """Test empty text message returns error."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("   "))

        assert "can only process text or receipt photos" in result

    def _make_photo_update(self) -> dict:
        """Create a mock Telegram photo update dict."""
        return {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "chat": {"id": self.chat_id, "type": "private"},
                "from": {"id": self.telegram_id, "is_bot": False, "first_name": "Test"},
                "photo": [
                    {"file_id": "small", "width": 320, "height": 240, "file_size": 1000},
                    {"file_id": "large", "width": 1280, "height": 960, "file_size": 50000},
                ],
            },
        }

    @pytest.mark.asyncio
    async def test_photo_not_linked_returns_link_instruction(self):
        """Test photo message when not linked returns link instruction."""
        self.db.scalar.return_value = None

        result = await process_telegram_update(self.db, self._make_photo_update())

        assert "not linked" in result

    @pytest.mark.asyncio
    async def test_photo_receipt_saves_transaction(self):
        """Test a photo receipt is OCR'd and saved (same concept as Android)."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        user = Profile(id=self.user_id, display_name="Test User")
        self.db.get.return_value = user

        account = Account(
            id=uuid.uuid4(),
            user_id=self.user_id,
            account_name="Cash",
            initial_balance=Decimal("0.00"),
            is_active=True,
        )
        category = Category(
            id=uuid.uuid4(),
            name="Other",
            type="expense",
            is_active=True,
            user_id=None,
        )
        tx = Transaction(id=uuid.uuid4(), user_id=self.user_id, type="expense")
        tx.total_amount = Decimal("42000")
        tx.note = "Mixue"
        tx.items = []

        from app.core.receipt_ocr import ParsedReceipt, ReceiptItem

        parsed = ParsedReceipt(
            type="expense",
            merchant="Mixue",
            date="2026-08-25",
            items=[
                ReceiptItem(
                    name="Ice Cream Tofee Hazelnut Latte (M)",
                    qty=Decimal("2"),
                    price=Decimal("21000"),
                )
            ],
        )

        with (
            patch(
                "app.core.telegram_service._download_telegram_file",
                new=AsyncMock(return_value=b"fake-image-bytes"),
            ),
            patch(
                "app.core.telegram_service.parse_receipt_image",
                new=AsyncMock(return_value=parsed),
            ),
            patch("app.core.telegram_service.get_or_create_category", return_value=category),
            patch("app.core.telegram_service._find_account_by_name", return_value=account),
            patch("app.core.telegram_service.get_or_create_default_account", return_value=account),
            patch(
                "app.core.telegram_service.create_transaction_internal",
                return_value=tx,
            ),
        ):
            result = await process_telegram_update(self.db, self._make_photo_update())

        assert "Saved!" in result
        assert "Mixue" in result

    @pytest.mark.asyncio
    async def test_photo_unreadable_returns_error(self):
        """Test an unreadable receipt photo returns a friendly error."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        with (
            patch(
                "app.core.telegram_service._download_telegram_file",
                new=AsyncMock(return_value=b"fake-image-bytes"),
            ),
            patch(
                "app.core.telegram_service.parse_receipt_image",
                new=AsyncMock(return_value=None),
            ),
        ):
            result = await process_telegram_update(self.db, self._make_photo_update())

        assert "couldn't read" in result

    @pytest.mark.asyncio
    async def test_non_text_message_returns_none(self):
        """Test non-text message (e.g., sticker) returns None."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "chat": {"id": self.chat_id, "type": "private"},
                "from": {"id": self.telegram_id, "is_bot": False, "first_name": "Test"},
                "sticker": {"file_id": "sticker_id"},
            },
        }

        result = await process_telegram_update(self.db, update)

        assert result is None
