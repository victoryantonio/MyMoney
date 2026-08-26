"""
Telegram SSO account linking — v2 (Supabase Auth).

Flow (v2, rebuilt in Fase 2 — the v1 email/password form is gone because
Supabase Auth owns credentials; there is no local password verification):

  1. User types /start in the bot → `process_telegram_update` generates a
     short-lived JWT (type `telegram_link`, 10 min) and sends the user a
     link: GET /api/telegram/link?token=<JWT>.

  2. User opens the link → backend validates the JWT and serves a minimal
     HTML page. The page asks for the user's email and sends a Supabase OTP
     to it (client-side, via the anon key which is safe for clients).

  3. User enters the OTP → the page exchanges it with Supabase
     (`/auth/v1/verify`, type=email) for a session access_token, then calls
     POST /api/telegram/link/confirm {link_token, access_token}.

  4. Backend verifies the Supabase JWT via JWKS → user_id, decodes
     link_token → telegram_id, and upserts the TelegramLink row
     (relink semantics: one telegram_id ↔ one profile).

Phase 4 (Flutter app) will migrate the inline HTML to a proper template
engine; for now we keep it inline to avoid adding Jinja2.
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.responses import HTMLResponse
from jose import JWTError
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import SupabaseJWTError, decode_token, verify_supabase_jwt
from app.db.session import get_db
from app.models.profile import Profile
from app.models.telegram_link import TelegramLink

log = structlog.get_logger()
router = APIRouter(prefix="/api/telegram", tags=["Telegram Linking"])

# ── Minimal inline HTML template ──────────────────────────────────────────────
# Branding follows DESIGN.md §3/§5 tokens (dusty slate blue, Manrope,
# card radius 12px, field radius 8px). Placeholders are replaced with
# .replace() so the CSS braces don't need escaping.

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
      --ok-bg: #EFF7F0;
      --ok-border: #B9DCC0;
      --ok-text: #2E7D46;
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
        --ok-bg: #1E3322;
        --ok-border: #2E5A3A;
        --ok-text: #7FC494;
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
      border: 1px solid var(--outline); border-radius: 8px; /* DESIGN.md §5: field = 8px */
      font-size: 0.95rem; font-family: inherit; color: var(--on-surface);
      background: var(--surface-card); outline: none;
      transition: border-color 0.15s, box-shadow 0.15s;
    }
    input:focus { border-color: var(--primary); box-shadow: 0 0 0 3px var(--primary-container); }
    input:disabled { opacity: 0.55; cursor: not-allowed; }
    .field { margin-bottom: 1.25rem; }
    button {
      width: 100%; padding: 0.75rem; background: var(--primary); color: var(--on-primary);
      border: none; border-radius: 8px; font-size: 1rem; font-weight: 600;
      font-family: inherit; cursor: pointer; transition: background 0.15s;
    }
    button:hover { background: var(--primary-hover); }
    button:disabled { opacity: 0.55; cursor: not-allowed; }
    .notice {
      background: var(--error-bg); border: 1px solid var(--error-border); border-radius: 8px;
      padding: 0.7rem 1rem; color: var(--error-text); font-size: 0.85rem;
      margin-bottom: 1rem; line-height: 1.4; display: none;
    }
    .notice.ok {
      background: var(--ok-bg); border-color: var(--ok-border); color: var(--ok-text);
    }
    .hint { font-size: 0.8rem; color: var(--on-surface-variant); margin-top: 0.5rem; line-height: 1.4; }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img class="brand-mark" src="/static/icon.png" alt="MyMoney">
      <span class="brand-name">MyMoney</span>
    </div>
    <h1>Link your Telegram account</h1>
    <p class="subtitle">Enter the email registered to your MyMoney account. We'll send a one-time code to verify it's you.</p>
    <div id="notice" class="notice"></div>
    <form id="otp-form" onsubmit="sendCode(event)">
      <div class="field">
        <label for="email">Email</label>
        <input type="email" id="email" required placeholder="you@email.com" autocomplete="email">
      </div>
      <button type="submit" id="send-btn">Send code</button>
    </form>
    <form id="verify-form" onsubmit="verifyCode(event)" style="display:none">
      <div class="field">
        <label for="otp">One-time code</label>
        <input type="text" id="otp" required placeholder="000000" inputmode="numeric" autocomplete="one-time-code">
      </div>
      <button type="submit" id="verify-btn">Verify &amp; link</button>
      <p class="hint">Check your inbox — the code expires in a few minutes. You can also use the password reset link if you prefer that flow.</p>
    </form>
  </div>
  <script>
    const SUPABASE_URL = "__SUPABASE_URL__";
    const SUPABASE_ANON_KEY = "__SUPABASE_ANON_KEY__";
    const LINK_TOKEN = "__TOKEN__";
    let email = "";
    const notice = document.getElementById("notice");

    function show(message, ok) {
      notice.textContent = message;
      notice.classList.toggle("ok", !!ok);
      notice.style.display = "block";
    }

    async function sendCode(event) {
      event.preventDefault();
      email = document.getElementById("email").value.trim();
      const btn = document.getElementById("send-btn");
      btn.disabled = true;
      btn.textContent = "Sending…";
      try {
        const res = await fetch(SUPABASE_URL + "/auth/v1/otp", {
          method: "POST",
          headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ email: email, create_user: false })
        });
        if (res.status === 429) { show("Too many requests — please wait a minute and try again."); return; }
        if (!res.ok) { show("Could not send the code. Please check the email and try again."); return; }
        document.getElementById("otp-form").style.display = "none";
        document.getElementById("verify-form").style.display = "block";
        show("Code sent to " + email, true);
      } catch (err) {
        show("Network error — please try again.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Send code";
      }
    }

    async function verifyCode(event) {
      event.preventDefault();
      const otp = document.getElementById("otp").value.trim();
      const btn = document.getElementById("verify-btn");
      btn.disabled = true;
      btn.textContent = "Verifying…";
      try {
        const verify = await fetch(SUPABASE_URL + "/auth/v1/verify", {
          method: "POST",
          headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ type: "email", email: email, token: otp })
        });
        const data = await verify.json();
        if (!verify.ok || !data.access_token) {
          show("Invalid or expired code. Please try again.");
          return;
        }
        const confirm = await fetch("/api/telegram/link/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ link_token: LINK_TOKEN, access_token: data.access_token })
        });
        if (confirm.ok) {
          document.getElementById("verify-form").style.display = "none";
          show("✅ Your Telegram account is now linked! Go back to Telegram and try again.", true);
        } else {
          const err = await confirm.json().catch(() => ({}));
          show("Could not link: " + (err.detail || "unknown error. The link may have expired — send /start again."));
        }
      } catch (err) {
        show("Network error — please try again.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Verify & link";
      }
    }
  </script>
</body>
</html>"""


class LinkConfirmRequest(BaseModel):
    link_token: str
    access_token: str


@router.get("/link", response_class=HTMLResponse)
async def link_page(request: Request, token: str) -> HTMLResponse:
    """Serve the linking page. Validates the short-lived telegram_link JWT first."""
    try:
        decode_token(token, "telegram_link")
    except JWTError as exc:
        log.info("telegram_link_invalid_token", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link. Send /start to the bot again for a fresh link.",
        ) from exc

    html = (
        _LINK_FORM_HTML.replace("__TOKEN__", token)
        .replace("__SUPABASE_URL__", settings.supabase_url)
        .replace("__SUPABASE_ANON_KEY__", settings.supabase_anon_key)
    )
    return HTMLResponse(html)


@router.post("/link/confirm")
@limiter.limit("10/minute")
async def confirm_link(
    request: Request,
    body: LinkConfirmRequest,
    db: Session = Depends(get_db),
) -> dict:
    """
    Verify the Supabase session from the OTP flow, decode the link token,
    and upsert the TelegramLink mapping (relink semantics).
    """
    # 1) Decode the short-lived linking token → telegram_id
    try:
        telegram_id = int(decode_token(body.link_token, "telegram_link"))
    except (JWTError, ValueError) as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid or expired link token.",
        ) from exc

    # 2) Verify the Supabase access token (JWKS) → auth.users UUID
    try:
        user_id = uuid.UUID(verify_supabase_jwt(body.access_token))
    except (SupabaseJWTError, ValueError) as exc:
        log.warning("telegram_link_invalid_supabase_token", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid Supabase session. Please verify your email code again.",
        ) from exc

    # 3) The profile row must exist (created by the Supabase trigger)
    profile = db.get(Profile, user_id)
    if profile is None:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Account not found.")

    # 4) Upsert with relink semantics: one telegram_id ↔ one profile.
    existing = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == telegram_id))
    if existing is not None and existing.user_id == user_id:
        db.commit()
        return {"ok": True}  # already linked — idempotent

    if existing is not None:
        db.delete(existing)
        db.flush()
    other = db.scalar(select(TelegramLink).where(TelegramLink.user_id == user_id))
    if other is not None:
        db.delete(other)
        db.flush()

    db.add(TelegramLink(id=uuid.uuid4(), user_id=user_id, telegram_id=telegram_id))
    db.commit()
    log.info(
        "telegram_link_created",
        user_id=str(user_id),
        telegram_id=telegram_id,
    )
    return {"ok": True}
