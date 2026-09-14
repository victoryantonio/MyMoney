"""
Telegram Webhook API endpoint.

Two accepted auth paths (either is sufficient):
  1. Service-to-service (primary, production): the Node bot forwards updates
     with header `X-Bot-Token` == `BOT_SERVICE_TOKEN`.
  2. Direct Telegram → backend (dev fallback): header
     `X-Telegram-Bot-Api-Secret-Token` == `TELEGRAM_WEBHOOK_SECRET`.

Either way we must answer 200 OK fast; business logic runs in the background
(LLM/OCR can take seconds) and replies are sent via the Bot API.

Idempotency: INSERT processed_updates(update_id) ON CONFLICT DO NOTHING.
Duplicates are ACKed but not processed. Background work uses its own Session.
"""

from datetime import UTC, datetime

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.telegram_service import process_telegram_update
from app.db.session import SessionLocal, get_db
from app.models.processed_update import ProcessedUpdate

log = structlog.get_logger()
router = APIRouter(prefix="/api/telegram", tags=["Telegram Webhook"])


def parse_update_id(update: dict) -> int | None:
    """Return a Telegram update_id, or None if missing/invalid."""
    raw = update.get("update_id") if isinstance(update, dict) else None
    if isinstance(raw, bool) or raw is None:
        return None
    if isinstance(raw, int):
        return raw
    if isinstance(raw, str) and raw.strip().lstrip("-").isdigit():
        return int(raw.strip())
    return None


def try_claim_update(db: Session, update_id: int) -> bool:
    """Insert processed_updates row. True if this request owns the update."""
    stmt = (
        insert(ProcessedUpdate)
        .values(update_id=update_id, status="received")
        .on_conflict_do_nothing(index_elements=["update_id"])
        .returning(ProcessedUpdate.update_id)
    )
    claimed = db.execute(stmt).fetchone() is not None
    db.commit()
    return claimed


def _chat_id_from_update(update: dict) -> int | None:
    message = update.get("message") if isinstance(update, dict) else None
    if not isinstance(message, dict):
        return None
    chat = message.get("chat")
    if not isinstance(chat, dict):
        return None
    chat_id = chat.get("id")
    if isinstance(chat_id, bool) or chat_id is None:
        return None
    try:
        return int(chat_id)
    except (TypeError, ValueError):
        return None


async def send_telegram_message(chat_id: int, text: str) -> None:
    """Send a text message back to the Telegram user via the Bot API."""
    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/sendMessage"
    payload = {"chat_id": chat_id, "text": text}

    async with httpx.AsyncClient() as client:
        try:
            resp = await client.post(url, json=payload, timeout=10.0)
            resp.raise_for_status()
        except httpx.HTTPError as e:
            log.error("telegram_send_message_failed", error=str(e), chat_id=chat_id)


async def background_process_update(update: dict) -> None:
    """
    Process the update in the background with a dedicated DB session.

    Must not use the request Session (it is closed when the webhook returns).
    Exceptions are logged and marked failed; they must not escape the task.
    """
    update_id = parse_update_id(update)
    db = SessionLocal()
    try:
        if update_id is not None:
            row = db.get(ProcessedUpdate, update_id)
            if row is not None:
                row.status = "processing"
                db.commit()

        reply_text = await process_telegram_update(db, update)
        chat_id = _chat_id_from_update(update)
        if reply_text and chat_id is not None:
            await send_telegram_message(chat_id, reply_text)

        if update_id is not None:
            row = db.get(ProcessedUpdate, update_id)
            if row is not None:
                row.status = "done"
                row.processed_at = datetime.now(UTC)
                db.commit()
    except Exception as e:
        log.exception(
            "telegram_update_processing_failed",
            error=str(e),
            update_id=update_id,
        )
        try:
            if update_id is not None:
                row = db.get(ProcessedUpdate, update_id)
                if row is not None:
                    row.status = "failed"
                    row.error = str(e)[:2000]
                    db.commit()
        except Exception:
            log.exception("telegram_update_failed_status_write", update_id=update_id)
    finally:
        db.close()


@router.post("/webhook")
@limiter.limit("20/minute")
async def telegram_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    x_bot_token: str | None = Header(default=None),
    x_telegram_bot_api_secret_token: str | None = Header(default=None),
    db: Session = Depends(get_db),
) -> dict:
    """
    Telegram webhook endpoint.

    Auth: accepts `X-Bot-Token` (service-to-service from the Node bot) OR the
    Telegram `X-Telegram-Bot-Api-Secret-Token` (direct fallback). Both must
    match their configured secret, otherwise 403.

    Must return 200 OK fast. The actual processing happens in the background
    only after a successful idempotency claim. Rate-limited to 20/min per IP.
    """
    bot_ok = x_bot_token == settings.bot_service_token
    secret_ok = x_telegram_bot_api_secret_token == settings.telegram_webhook_secret
    if not (bot_ok or secret_ok):
        log.warning(
            "telegram_webhook_invalid_auth",
            has_bot_token=x_bot_token is not None,
            has_telegram_secret=x_telegram_bot_api_secret_token is not None,
        )
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Invalid secret")

    try:
        update = await request.json()
    except Exception:
        log.warning("telegram_webhook_invalid_json")
        return {"status": "ok"}

    if not isinstance(update, dict):
        return {"status": "ok"}

    update_id = parse_update_id(update)
    log.info("telegram_update_received", update_id=update_id)

    if update_id is None:
        log.warning("telegram_webhook_missing_update_id")
        return {"status": "ok"}

    claimed = try_claim_update(db, update_id)
    if not claimed:
        log.info("telegram_webhook_duplicate", update_id=update_id)
        return {"status": "ok"}

    background_tasks.add_task(background_process_update, update)
    return {"status": "ok"}


@router.post("/register-webhook", include_in_schema=False)
async def register_webhook(x_admin_token: str | None = Header(default=None)) -> dict:
    """
    Utility endpoint to register the Node bot's public URL with Telegram API.

    The bot (thin client) is the webhook target; it verifies the Telegram
    secret, then forwards updates to this backend with `X-Bot-Token`.
    Used during deployment (Fase 2 cutover).
    """
    if x_admin_token != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN)

    url = f"https://api.telegram.org/bot{settings.telegram_bot_token}/setWebhook"
    webhook_url = f"{settings.bot_public_url}/webhook"

    payload = {
        "url": webhook_url,
        "secret_token": settings.telegram_webhook_secret,
    }

    async with httpx.AsyncClient() as client:
        resp = await client.post(url, json=payload)
        return resp.json()
