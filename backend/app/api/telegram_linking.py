"""
Telegram SSO account linking routes.

Flow:
  1. The Telegram bot calls POST /api/telegram/generate-link?telegram_id=<id>
     (internal call, protected by webhook secret header)
     → Returns a short-lived signed link URL the bot sends to the user.

  2. User clicks the link:  GET /api/telegram/link?token=<JWT>
     → Backend validates the token, serves a minimal HTML login form.

  3. User submits their MyMoney credentials:  POST /api/telegram/link
     → Backend verifies email/password, validates the JWT token,
       creates the TelegramLink record, and shows a success page.
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from jose import JWTError
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_telegram_link_token,
    decode_token,
    verify_password,
)
from app.db.session import get_db
from app.models.telegram_link import TelegramLink
from app.models.user import User

log = structlog.get_logger()
router = APIRouter(prefix="/api/telegram", tags=["Telegram SSO"])

# ── Minimal inline HTML templates ─────────────────────────────────────────────
# We use inline HTML to avoid adding Jinja2 as a dependency for now.
# Phase 4 will migrate this to a proper template engine.

_LINK_FORM_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Link Telegram — MyMoney</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f6f8; display: flex; align-items: center;
            justify-content: center; min-height: 100vh; padding: 1rem; }}
    .card {{ background: white; border-radius: 12px; padding: 2.5rem 2rem;
             max-width: 400px; width: 100%; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .logo {{ font-size: 2rem; margin-bottom: 0.5rem; }}
    h1 {{ font-size: 1.25rem; color: #1a202c; margin-bottom: 0.5rem; }}
    p {{ font-size: 0.9rem; color: #718096; margin-bottom: 1.5rem; }}
    label {{ display: block; font-size: 0.875rem; font-weight: 500;
             color: #4a5568; margin-bottom: 0.35rem; }}
    input {{ width: 100%; padding: 0.6rem 0.75rem; border: 1px solid #e2e8f0;
             border-radius: 8px; font-size: 0.95rem; outline: none;
             transition: border-color 0.15s; }}
    input:focus {{ border-color: #667eea; }}
    .field {{ margin-bottom: 1.25rem; }}
    button {{ width: 100%; padding: 0.75rem; background: #667eea;
              color: white; border: none; border-radius: 8px; font-size: 1rem;
              font-weight: 600; cursor: pointer; transition: background 0.15s; }}
    button:hover {{ background: #5a6fe8; }}
    .error {{ background: #fff5f5; border: 1px solid #feb2b2; border-radius: 8px;
              padding: 0.75rem 1rem; color: #c53030; font-size: 0.875rem;
              margin-bottom: 1rem; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="logo">💸</div>
    <h1>Link your Telegram account</h1>
    <p>Enter your MyMoney credentials to connect your Telegram account.</p>
    {error_block}
    <form method="post">
      <input type="hidden" name="token" value="{token}">
      <div class="field">
        <label for="email">Email</label>
        <input type="email" id="email" name="email" required placeholder="you@email.com">
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input type="password" id="password" name="password" required placeholder="••••••••">
      </div>
      <button type="submit">Link Account</button>
    </form>
  </div>
</body>
</html>"""

_SUCCESS_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Linked — MyMoney</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            background: #f4f6f8; display: flex; align-items: center;
            justify-content: center; min-height: 100vh; }}
    .card {{ background: white; border-radius: 12px; padding: 2.5rem 2rem;
             max-width: 400px; width: 100%; text-align: center;
             box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .icon {{ font-size: 3rem; margin-bottom: 1rem; }}
    h1 {{ font-size: 1.25rem; color: #22543d; margin-bottom: 0.5rem; }}
    p {{ font-size: 0.9rem; color: #718096; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">✅</div>
    <h1>Account linked successfully!</h1>
    <p>You can now close this page and return to the MyMoney Telegram bot.</p>
  </div>
</body>
</html>"""

_EXPIRED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <title>Link Expired — MyMoney</title>
  <style>
    body {{ font-family: sans-serif; display: flex; align-items: center;
            justify-content: center; min-height: 100vh; background: #f4f6f8; }}
    .card {{ background: white; border-radius: 12px; padding: 2.5rem;
             text-align: center; max-width: 380px; box-shadow: 0 4px 24px rgba(0,0,0,0.08); }}
    .icon {{ font-size: 3rem; }}
    h1 {{ color: #c53030; margin: 0.75rem 0 0.5rem; font-size: 1.25rem; }}
    p {{ color: #718096; font-size: 0.9rem; }}
  </style>
</head>
<body>
  <div class="card">
    <div class="icon">⏰</div>
    <h1>Link expired</h1>
    <p>This link has expired (valid for 10 minutes). Please send /start again in the bot to get a new link.</p>
  </div>
</body>
</html>"""


# ── Helper ─────────────────────────────────────────────────────────────────────


def _render_form(token: str, error: str | None = None) -> str:
    error_block = f'<div class="error">{error}</div>' if error else ""
    return _LINK_FORM_HTML.format(token=token, error_block=error_block)


# ── Endpoints ──────────────────────────────────────────────────────────────────


@router.post(
    "/generate-link",
    summary="Generate a Telegram account linking URL (internal bot use only)",
    response_model=dict,
)
def generate_link(
    request: Request,
    telegram_id: int,
) -> dict:
    """
    Generate a short-lived URL the bot sends to the user to link their account.

    SECURITY: This endpoint is restricted to callers that supply the correct
    X-Telegram-Bot-Api-Secret-Token header (same token Telegram uses for webhooks).
    """
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token", "")
    if secret != settings.telegram_webhook_secret:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden")

    token = create_telegram_link_token(telegram_id)
    link_url = f"{settings.app_base_url}/api/telegram/link?token={token}"
    return {"url": link_url, "expires_in_seconds": 600}


@router.get("/link", response_class=HTMLResponse, summary="Telegram account linking form")
def get_link_form(token: str) -> HTMLResponse:
    """Validate the token and serve the login form (or an expired-link page)."""
    try:
        decode_token(token, expected_type="telegram_link")
    except JWTError:
        return HTMLResponse(_EXPIRED_HTML, status_code=status.HTTP_400_BAD_REQUEST)

    return HTMLResponse(_render_form(token))


@router.post("/link", response_class=HTMLResponse, summary="Process Telegram account linking")
def post_link_form(
    token: str = Form(...),
    email: str = Form(...),
    password: str = Form(...),
    db: Session = Depends(get_db),
) -> HTMLResponse:
    """
    Process the linking form submission.

    Steps:
      1. Re-validate the JWT token (it could have expired while the user filled the form)
      2. Authenticate user credentials
      3. Check for existing link (prevent duplicate linking)
      4. Create TelegramLink record
    """
    # Step 1: Re-validate token
    try:
        telegram_id_str = decode_token(token, expected_type="telegram_link")
        telegram_id = int(telegram_id_str)
    except (JWTError, ValueError):
        return HTMLResponse(_EXPIRED_HTML, status_code=status.HTTP_400_BAD_REQUEST)

    _invalid_creds_error = "Invalid email or password. Please try again."

    # Step 2: Authenticate the user
    user = db.scalar(select(User).where(User.email == email.lower()))
    if user is None or not verify_password(password, user.password_hash):
        return HTMLResponse(
            _render_form(token, error=_invalid_creds_error),
            status_code=status.HTTP_401_UNAUTHORIZED,
        )

    if not user.is_active:
        return HTMLResponse(
            _render_form(token, error="Your account is deactivated."),
            status_code=status.HTTP_403_FORBIDDEN,
        )

    # Step 3: Check for existing telegram_id already linked to ANOTHER user
    existing_telegram = db.scalar(
        select(TelegramLink).where(TelegramLink.telegram_id == telegram_id)
    )
    if existing_telegram is not None and existing_telegram.user_id != user.id:
        return HTMLResponse(
            _render_form(token, error="This Telegram account is already linked to another user."),
            status_code=status.HTTP_409_CONFLICT,
        )

    # If this user already has their Telegram linked (idempotent)
    existing_user_link = db.scalar(select(TelegramLink).where(TelegramLink.user_id == user.id))
    if existing_user_link is not None:
        # Update the telegram_id in case the user changed their Telegram account
        existing_user_link.telegram_id = telegram_id
        db.commit()
        log.info("telegram_link_updated", user_id=str(user.id), telegram_id=telegram_id)
        return HTMLResponse(_SUCCESS_HTML)

    # Step 4: Create the link
    link = TelegramLink(
        id=uuid.uuid4(),
        user_id=user.id,
        telegram_id=telegram_id,
        linked_at=datetime.now(UTC),
    )
    db.add(link)
    db.commit()

    log.info("telegram_link_created", user_id=str(user.id), telegram_id=telegram_id)
    return HTMLResponse(_SUCCESS_HTML)
