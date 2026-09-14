"""
API tests for the Telegram webhook endpoint (Fase 2).

Covers:
  - 403 without / with wrong auth headers (before any DB write)
  - 200 with `X-Bot-Token` (service-to-service, production path)
  - 200 with `X-Telegram-Bot-Api-Secret-Token` (direct fallback)
  - idempotency on duplicate update_id
  - missing update_id ACKs without processing
  - background task uses its own SessionLocal, not the request session

The background processing is mocked — the real LLM/OCR pipeline must never
run inside unit tests.
"""

import time
from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.config import settings
from app.main import app
from app.models.processed_update import ProcessedUpdate

client = TestClient(app)


def _update(update_id: int | None = None, **extra) -> dict:
    uid = update_id if update_id is not None else time.time_ns()
    body = {
        "update_id": uid,
        "message": {
            "message_id": 1,
            "date": 1234567890,
            "chat": {"id": 123456789, "type": "private"},
            "from": {"id": 123456789, "is_bot": False, "first_name": "Test"},
            "text": "Beli kopi 15k",
        },
    }
    body.update(extra)
    return body


@pytest.fixture
def webhook_secrets():
    """Pin deterministic secrets so tests pass regardless of .env values."""
    with (
        patch.object(settings, "bot_service_token", "test-bot-token"),
        patch.object(settings, "telegram_webhook_secret", "test-webhook-secret"),
    ):
        yield


def _bot_headers() -> dict[str, str]:
    return {"X-Bot-Token": "test-bot-token"}


def test_webhook_403_without_headers(webhook_secrets, db):
    body = _update()
    resp = client.post("/api/telegram/webhook", json=body)
    assert resp.status_code == 403
    assert db.get(ProcessedUpdate, body["update_id"]) is None


def test_webhook_403_wrong_bot_token(webhook_secrets, db):
    body = _update()
    resp = client.post("/api/telegram/webhook", json=body, headers={"X-Bot-Token": "wrong"})
    assert resp.status_code == 403
    assert db.get(ProcessedUpdate, body["update_id"]) is None


def test_webhook_200_with_bot_token(webhook_secrets):
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        resp = client.post(
            "/api/telegram/webhook",
            json=_update(),
            headers=_bot_headers(),
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_task.assert_awaited_once()
    assert mock_task.await_args.args == (mock_task.await_args.args[0],)
    assert len(mock_task.await_args.args) == 1


def test_webhook_200_with_telegram_secret(webhook_secrets):
    """Direct Telegram → backend fallback must keep working."""
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        resp = client.post(
            "/api/telegram/webhook",
            json=_update(),
            headers={"X-Telegram-Bot-Api-Secret-Token": "test-webhook-secret"},
        )
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_task.assert_awaited_once()


def test_webhook_duplicate_update_id_processed_once(webhook_secrets):
    body = _update()
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        first = client.post("/api/telegram/webhook", json=body, headers=_bot_headers())
        second = client.post("/api/telegram/webhook", json=body, headers=_bot_headers())
    assert first.status_code == 200
    assert second.status_code == 200
    assert first.json() == second.json() == {"status": "ok"}
    mock_task.assert_awaited_once()


def test_webhook_missing_update_id_acks_without_process(webhook_secrets):
    body = _update()
    del body["update_id"]
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        resp = client.post("/api/telegram/webhook", json=body, headers=_bot_headers())
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}
    mock_task.assert_not_awaited()


def test_webhook_invalid_update_id_acks_without_process(webhook_secrets):
    with patch(
        "app.api.telegram_webhook.background_process_update", new_callable=AsyncMock
    ) as mock_task:
        resp = client.post(
            "/api/telegram/webhook",
            json=_update(update_id="not-an-id"),
            headers=_bot_headers(),
        )
    assert resp.status_code == 200
    mock_task.assert_not_awaited()


def test_background_uses_own_session_not_request_db(webhook_secrets):
    """Background must open SessionLocal itself; request session is already closed."""
    from app.db.session import SessionLocal as RealSessionLocal

    opened: list = []

    def tracking_factory():
        session = RealSessionLocal()
        opened.append(session)
        return session

    process = AsyncMock(return_value="saved")
    with (
        patch("app.api.telegram_webhook.SessionLocal", side_effect=tracking_factory),
        patch("app.api.telegram_webhook.process_telegram_update", process),
        patch("app.api.telegram_webhook.send_telegram_message", new_callable=AsyncMock) as send,
    ):
        body = _update()
        resp = client.post("/api/telegram/webhook", json=body, headers=_bot_headers())

    assert resp.status_code == 200
    process.assert_awaited_once()
    assert opened, "background task must open SessionLocal()"
    assert process.await_args.args[0] is opened[0]
    send.assert_awaited_once()


def test_processing_failure_marks_failed_keeps_row(webhook_secrets, db):
    process = AsyncMock(side_effect=RuntimeError("boom"))
    with (
        patch("app.api.telegram_webhook.process_telegram_update", process),
        patch("app.api.telegram_webhook.send_telegram_message", new_callable=AsyncMock),
    ):
        body = _update()
        resp = client.post("/api/telegram/webhook", json=body, headers=_bot_headers())
    assert resp.status_code == 200
    db.expire_all()
    row = db.get(ProcessedUpdate, body["update_id"])
    assert row is not None
    assert row.status == "failed"
    assert row.error is not None and "boom" in row.error
