"""
Unit tests for telegram_service.py — testing /start, /undo, /edit, and text parsing.
"""

import uuid
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from app.core.telegram_service import process_telegram_update
from app.models.category import Category
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction
from app.models.user import User


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
        user = User(id=self.user_id, display_name="Test User", email="test@example.com", password_hash="hash")
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
        """Test /edit with empty arguments returns error."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("/edit   "))

        assert "Please provide the new transaction details" in result

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

        with patch("app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = None

            result = await process_telegram_update(self.db, self._make_update("/edit hello world"))

        assert "couldn't understand the new transaction" in result

    @pytest.mark.asyncio
    async def test_edit_success(self):
        """Test successful /edit updates transaction."""
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
            account_id=uuid.uuid4(),
            source="telegram",
            note="Bensin",
        )
        self.db.scalar.side_effect = [link, old_tx, new_category]

        with patch("app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction
            mock_parse.return_value = ParsedTransaction(
                type="expense",
                amount=Decimal("50000"),
                category="Transport",
                note="Bensin"
            )
            with patch("app.core.telegram_service.update_transaction_internal") as mock_update:
                mock_update.return_value = updated_tx

                result = await process_telegram_update(self.db, self._make_update("/edit bensin 50rb"))

        assert "Updated!" in result
        assert "50,000" in result
        assert "Transport" in result
        assert "Bensin" in result
        mock_update.assert_called_once()

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

        with patch("app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock) as mock_parse:
            mock_parse.return_value = None

            result = await process_telegram_update(self.db, self._make_update("Hello world"))

        assert "couldn't understand that transaction" in result

    @pytest.mark.asyncio
    async def test_text_parsing_success(self):
        """Test successful text parsing creates transaction."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        account = MagicMock()
        account.id = uuid.uuid4()
        category = Category(id=uuid.uuid4(), name="Food", type="expense")
        new_tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=category.id,
            account_id=account.id,
            source="telegram",
            note="Makan siang",
        )
        self.db.scalar.side_effect = [link, account, category]

        with patch("app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction
            mock_parse.return_value = ParsedTransaction(
                type="expense",
                amount=Decimal("35000"),
                category="Food",
                note="Makan siang"
            )
            with patch("app.core.telegram_service.create_transaction_internal") as mock_create:
                mock_create.return_value = new_tx

                result = await process_telegram_update(self.db, self._make_update("Makan siang 35rb"))

        assert "Saved!" in result
        assert "35,000" in result
        assert "Food" in result
        assert "Makan siang" in result
        mock_create.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_uses_original_text_as_note_when_none(self):
        """Test that original text is used as note when LLM doesn't provide one."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        account = MagicMock()
        account.id = uuid.uuid4()
        category = Category(id=uuid.uuid4(), name="Food", type="expense")
        new_tx = Transaction(
            id=uuid.uuid4(),
            user_id=self.user_id,
            type="expense",
            total_amount=Decimal("35000"),
            category_id=category.id,
            account_id=account.id,
            source="telegram",
            note="Makan siang 35rb",  # original text used as note
        )
        self.db.scalar.side_effect = [link, account, category]

        with patch("app.core.telegram_service.parse_text_to_transaction", new_callable=AsyncMock) as mock_parse:
            from app.core.nlu_parser import ParsedTransaction
            mock_parse.return_value = ParsedTransaction(
                type="expense",
                amount=Decimal("35000"),
                category="Food",
                note=None  # LLM didn't provide note
            )
            with patch("app.core.telegram_service.create_transaction_internal") as mock_create:
                mock_create.return_value = new_tx

                result = await process_telegram_update(self.db, self._make_update("Makan siang 35rb"))

        assert "Makan siang 35rb" in result
        # Verify create_transaction_internal was called with original text as note
        call_args = mock_create.call_args
        assert call_args.kwargs["note"] == "Makan siang 35rb"

    @pytest.mark.asyncio
    async def test_empty_text_returns_error(self):
        """Test empty text message returns error."""
        link = TelegramLink(id=uuid.uuid4(), user_id=self.user_id, telegram_id=self.telegram_id)
        self.db.scalar.return_value = link

        result = await process_telegram_update(self.db, self._make_update("   "))

        assert "can only process text messages" in result

    @pytest.mark.asyncio
    async def test_non_text_message_returns_none(self):
        """Test non-text message (e.g., photo) returns None."""
        update = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "date": 1234567890,
                "chat": {"id": self.chat_id, "type": "private"},
                "from": {"id": self.telegram_id, "is_bot": False, "first_name": "Test"},
                "photo": [{"file_id": "abc"}],
            },
        }

        result = await process_telegram_update(self.db, update)

        assert result is None