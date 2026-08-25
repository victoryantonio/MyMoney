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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* DESIGN.md §3 tokens — dusty slate blue, light + dark */
    :root {
      --surface: #F5F7FA;
      --surface-card: #FFFFFF;
      --on-surface: #1A2233;
      --on-surface-variant: #556070;
      --primary: #3B5B8C;
      --primary-hover: #2F4A74;
      --on-primary: #FFFFFF;
      --primary-container: #D0DCF0;
      --outline: #D0D8E8;
      --error-bg: #FDF3F0;
      --error-border: #E5B8AC;
      --error-text: #A8503C;
      --shadow: rgba(26, 34, 51, 0.06);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --surface: #131B27;
        --surface-card: #1C2738;
        --on-surface: #E2E8F5;
        --on-surface-variant: #A0ABBE;
        --primary: #7B9ED4;
        --primary-hover: #8FB0DD;
        --on-primary: #131B27;
        --primary-container: #243554;
        --outline: #2C3D57;
        --error-bg: #3A2320;
        --error-border: #6E3B30;
        --error-text: #D18871;
        --shadow: rgba(0, 0, 0, 0.25);
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--surface);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 1rem;
    }
    .card {
      background: var(--surface-card);
      border: 1px solid var(--outline);
      border-radius: 12px; /* DESIGN.md §5: card = 12px, not extreme pill */
      padding: 2.5rem 2rem;
      max-width: 400px; width: 100%;
      box-shadow: var(--shadow);
    }
    .brand { display: flex; align-items: center; gap: 0.6rem; margin-bottom: 1.75rem; }
    .brand-mark {
      width: 36px; height: 36px; border-radius: 10px;
      object-fit: cover; display: block;
    }
    .brand-name { font-weight: 700; font-size: 1.1rem; color: var(--on-surface); }
    h1 { font-size: 1.25rem; font-weight: 600; color: var(--on-surface); margin-bottom: 0.4rem; }
    .subtitle { font-size: 0.9rem; color: var(--on-surface-variant); margin-bottom: 1.75rem; line-height: 1.5; }
    label { display: block; font-size: 0.8rem; font-weight: 600; color: var(--on-surface); margin-bottom: 0.35rem; }
    input {
      width: 100%; padding: 0.65rem 0.8rem;
      border: 1px solid var(--outline); border-radius: 8px; /* DESIGN.md §5: button/field = 8px */
      font-size: 0.95rem; font-family: inherit; color: var(--on-surface);
      background: var(--surface-card); outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-container); }
    .field { margin-bottom: 1.25rem; }
    button {
      width: 100%; padding: 0.75rem; background: var(--primary); color: var(--on-primary);
      border: none; border-radius: 8px; font-size: 1rem; font-weight: 600;
      font-family: inherit; cursor: pointer; transition: background 0.15s;
    }
    button:hover { background: var(--primary-hover); }
    .error {
      background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 8px;
      padding: 0.7rem 1rem; color: var(--error-text); font-size: 0.85rem;
      margin-bottom: 1rem; line-height: 1.4;
    }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img class="brand-mark" src="/static/icon.png" alt="MyMoney">
      <span class="brand-name">MyMoney</span>
    </div>
    <h1>Link your Telegram account</h1>
    <p class="subtitle">Enter your MyMoney credentials to connect your Telegram account.</p>
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
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* DESIGN.md §3 tokens — dusty slate blue, light + dark */
    :root {
      --surface: #F5F7FA;
      --surface-card: #FFFFFF;
      --on-surface: #1A2233;
      --on-surface-variant: #556070;
      --primary: #3B5B8C;
      --on-primary: #FFFFFF;
      --primary-container: #D0DCF0;
      --outline: #D0D8E8;
      --shadow: rgba(26, 34, 51, 0.06);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --surface: #131B27;
        --surface-card: #1C2738;
        --on-surface: #E2E8F5;
        --on-surface-variant: #A0ABBE;
        --primary: #7B9ED4;
        --on-primary: #131B27;
        --primary-container: #243554;
        --outline: #2C3D57;
        --shadow: rgba(0, 0, 0, 0.25);
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--surface);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 1rem;
    }
    .card {
      background: var(--surface-card);
      border: 1px solid var(--outline);
      border-radius: 12px; /* DESIGN.md §5: card = 12px */
      padding: 2.5rem 2rem;
      max-width: 400px; width: 100%; text-align: center;
      box-shadow: var(--shadow);
    }
    .brand { display: flex; align-items: center; justify-content: center; gap: 0.6rem; margin-bottom: 1.75rem; }
    .brand-mark {
      width: 36px; height: 36px; border-radius: 10px;
      object-fit: cover; display: block;
    }
    .brand-name { font-weight: 700; font-size: 1.1rem; color: var(--on-surface); }
    .icon-wrap {
      width: 56px; height: 56px; border-radius: 50%;
      background: var(--primary-container);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 1.25rem;
    }
    h1 { font-size: 1.25rem; font-weight: 600; color: var(--on-surface); margin-bottom: 0.5rem; }
    p { font-size: 0.9rem; color: var(--on-surface-variant); line-height: 1.5; }
    .closing { margin-top: 1.5rem; font-size: 0.78rem; color: var(--on-surface-variant); }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img class="brand-mark" src="/static/icon.png" alt="MyMoney">
      <span class="brand-name">MyMoney</span>
    </div>
    <div class="icon-wrap">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M20 6L9 17l-5-5" stroke="var(--primary)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round"/>
      </svg>
    </div>
    <h1>Account linked successfully!</h1>
    <p>You can now close this page and return to the MyMoney Telegram bot.</p>
    <p class="closing">This page will close automatically. If not, you can close it manually.</p>
  </div>
  <script>
    window.addEventListener('load', function () {
      setTimeout(function () {
        // Telegram in-app browser closes the tab when the page calls window.close().
        window.open('', '_self');
        window.close();
      }, 1200);
    });
  </script>
</body>
</html>"""

_EXPIRED_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <title>Link Expired — MyMoney</title>
  <link rel="preconnect" href="https://fonts.googleapis.com">
  <link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
  <link href="https://fonts.googleapis.com/css2?family=Manrope:wght@400;500;600;700&display=swap" rel="stylesheet">
  <style>
    /* DESIGN.md §3 tokens — dusty slate blue, light + dark */
    :root {
      --surface: #F5F7FA;
      --surface-card: #FFFFFF;
      --on-surface: #1A2233;
      --on-surface-variant: #556070;
      --primary: #3B5B8C;
      --on-primary: #FFFFFF;
      --primary-container: #D0DCF0;
      --outline: #D0D8E8;
      --shadow: rgba(26, 34, 51, 0.06);
    }
    @media (prefers-color-scheme: dark) {
      :root {
        --surface: #131B27;
        --surface-card: #1C2738;
        --on-surface: #E2E8F5;
        --on-surface-variant: #A0ABBE;
        --primary: #7B9ED4;
        --on-primary: #131B27;
        --primary-container: #243554;
        --outline: #2C3D57;
        --shadow: rgba(0, 0, 0, 0.25);
      }
    }
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body {
      font-family: 'Manrope', -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
      background: var(--surface);
      display: flex; align-items: center; justify-content: center;
      min-height: 100vh; padding: 1rem;
    }
    .card {
      background: var(--surface-card);
      border: 1px solid var(--outline);
      border-radius: 12px; /* DESIGN.md §5: card = 12px */
      padding: 2.5rem 2rem;
      max-width: 400px; width: 100%; text-align: center;
      box-shadow: var(--shadow);
    }
    .brand { display: flex; align-items: center; justify-content: center; gap: 0.6rem; margin-bottom: 1.75rem; }
    .brand-mark {
      width: 36px; height: 36px; border-radius: 10px;
      object-fit: cover; display: block;
    }
    .brand-name { font-weight: 700; font-size: 1.1rem; color: var(--on-surface); }
    .icon-wrap {
      width: 56px; height: 56px; border-radius: 50%;
      background: var(--primary-container);
      display: flex; align-items: center; justify-content: center;
      margin: 0 auto 1.25rem;
    }
    h1 { font-size: 1.25rem; font-weight: 600; color: var(--on-surface); margin-bottom: 0.5rem; }
    p { font-size: 0.9rem; color: var(--on-surface-variant); line-height: 1.5; }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img class="brand-mark" src="/static/icon.png" alt="MyMoney">
      <span class="brand-name">MyMoney</span>
    </div>
    <div class="icon-wrap">
      <svg width="28" height="28" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="12" cy="12" r="9" stroke="var(--primary)" stroke-width="2"/>
        <path d="M12 8v4l2.5 2.5" stroke="var(--primary)" stroke-width="2" stroke-linecap="round"/>
      </svg>
    </div>
    <h1>Link expired</h1>
    <p>This link has expired (valid for 10 minutes). Please send /start again in the bot to get a new link.</p>
  </div>
</body>
</html>"""


# ── Helper ─────────────────────────────────────────────────────────────────────


def _render_form(token: str, error: str | None = None) -> str:
    error_block = f'<div class="error">{error}</div>' if error else ""
    # .replace() (not .format()) so the CSS braces in the template stay unescaped.
    return (
        _LINK_FORM_HTML.replace("{token}", token).replace("{error_block}", error_block)
    )


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
