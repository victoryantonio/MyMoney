"""
Telegram Webhook API endpoint.

Two accepted auth paths (either is sufficient):
  1. Service-to-service (primary, production): the Node bot forwards updates
     with header `X-Bot-Token` == `BOT_SERVICE_TOKEN`.
  2. Direct Telegram → backend (dev fallback): header
     `X-Telegram-Bot-Api-Secret-Token` == `TELEGRAM_WEBHOOK_SECRET`.

Either way we must answer 200 OK fast; business logic runs in the background
(LLM/OCR can take seconds) and replies are sent via the Bot API.
"""

import httpx
import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, Header, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.telegram_service import process_telegram_update
from app.db.session import get_db

log = structlog.get_logger()
router = APIRouter(prefix="/api/telegram", tags=["Telegram Webhook"])


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


async def background_process_update(update: dict, db: Session) -> None:
    """
    Process the update in the background. We must respond to Telegram's POST
    with 200 OK immediately, so we don't hold the connection open while the LLM runs.
    """
    try:
        reply_text = await process_telegram_update(db, update)
        if reply_text and "message" in update:
            chat_id = update["message"]["chat"]["id"]
            await send_telegram_message(chat_id, reply_text)
    except Exception as e:
        log.exception("telegram_update_processing_failed", error=str(e))


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

    Must return 200 OK fast. The actual processing happens in the background.
    Rate-limited to 20/min per IP (CODING_RULES §2.10).
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

    update = await request.json()
    log.info("telegram_update_received", update_id=update.get("update_id"))

    # Schedule background processing so we return 200 immediately
    background_tasks.add_task(background_process_update, update, db)

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
