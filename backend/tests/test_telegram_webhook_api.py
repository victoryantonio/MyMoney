"""
API tests for the Telegram webhook endpoint (Fase 2).

Covers:
  - 403 without / with wrong auth headers
  - 200 with `X-Bot-Token` (service-to-service, production path)
  - 200 with `X-Telegram-Bot-Api-Secret-Token` (direct fallback)

The background processing is mocked — the real LLM/OCR pipeline must never
run inside unit tests.
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app

client = TestClient(app)

_UPDATE = {
    "update_id": 1,
    "message": {
        "message_id": 1,
        "date": 1234567890,
        "chat": {"id": 123456789, "type": "private"},
        "from": {"id": 123456789, "is_bot": False, "first_name": "Test"},
        "text": "Beli kopi 15k",
    },
}


@pytest.fixture
def webhook_secrets():
    """Pin deterministic secrets so tests pass regardless of .env values."""
    with (
        patch.object(settings, "bot_service_token", "test-bot-token"),
        patch.object(settings, "telegram_webhook_secret", "test-webhook-secret"),
    ):
        yield


def test_webhook_403_without_headers(webhook_secrets):
    resp = client.post("/api/telegram/webhook", json=_UPDATE)
    assert resp.status_code == 403


def test_webhook_403_wrong_bot_token(webhook_secrets):
    resp = client.post("/api/telegram/webhook", json=_UPDATE, headers={"X-Bot-Token": "wrong"})
    assert resp.status_code == 403


def test_webhook_200_with_bot_token(webhook_secrets):
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        resp = client.post(
            "/api/telegram/webhook",
            json=_UPDATE,
            headers={"X-Bot-Token": "test-bot-token"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_task.assert_awaited_once()


def test_webhook_200_with_telegram_secret(webhook_secrets):
    """Direct Telegram → backend fallback must keep working."""
    with patch("app.api.telegram_webhook.background_process_update", new_callable=AsyncMock):
        resp = client.post(
            "/api/telegram/webhook",
            json=_UPDATE,
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
