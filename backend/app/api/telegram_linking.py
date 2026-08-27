"""
Telegram SSO account linking — v2 (Supabase Auth).

Flow (v2, rebuilt in Fase 2 — the v1 email/password form is gone because
Supabase Auth owns credentials; there is no local password verification):

  1. User types /start in the bot → `process_telegram_update` generates a
     short-lived JWT (type `telegram_link`, 10 min) and sends the user a
     link: GET /api/telegram/link?token=<JWT>.

  2. User opens the link → backend validates the JWT and serves a minimal
     HTML page with an SSO-style login form (email + password). The page
     calls Supabase `POST /auth/v1/token?grant_type=password` directly with
     the anon key (client-safe) — no OTP entry in the linking flow.

  3. On success the page posts the session access_token to
     POST /api/telegram/link/confirm {link_token, access_token}; the tab
     auto-closes after the link is confirmed.

  4. Backend verifies the Supabase JWT via JWKS → user_id, decodes
     link_token → telegram_id, and upserts the TelegramLink row
     (relink semantics: one telegram_id ↔ one profile).

OTP / one-time-code emails are ONLY used outside this page:
  - forgot password → Supabase `POST /auth/v1/recover` (recovery email)
  - email verification after signup → Supabase `POST /auth/v1/resend`
    (type=signup), also offered on this page when the logged-in email is
    still unverified (email_confirmed_at == null).

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
    .hint a { color: var(--primary); text-decoration: none; font-weight: 600; }
    .hint a:hover { text-decoration: underline; }
    .row { display: flex; gap: 0.5rem; margin-top: 0.75rem; flex-wrap: wrap; }
    .row button { flex: 1; min-width: 150px; padding: 0.6rem 0.75rem; font-size: 0.85rem; }
    button.secondary {
      background: transparent; color: var(--primary);
      border: 1px solid var(--primary);
    }
    button.secondary:hover { background: var(--primary-container); }
    .success {
      background: var(--ok-bg); border: 1px solid var(--ok-border); border-radius: 8px;
      padding: 1.25rem 1rem; color: var(--ok-text); text-align: center; line-height: 1.5;
    }
    .success p:first-child { font-weight: 700; font-size: 1rem; }
  </style>
</head>
<body>
  <div class="card">
    <div class="brand">
      <img class="brand-mark" src="/static/icon.png" alt="MyMoney">
      <span class="brand-name">MyMoney</span>
    </div>
    <h1>Link your Telegram account</h1>
    <p class="subtitle">Log in with the email &amp; password of your MyMoney account to link it with Telegram. One-time codes are only used for password reset or email verification.</p>
    <div id="notice" class="notice"></div>

    <!-- Login (email & password — SSO style) -->
    <form id="login-form" onsubmit="login(event)">
      <div class="field">
        <label for="email">Email</label>
        <input type="email" id="email" required placeholder="you@email.com" autocomplete="email">
      </div>
      <div class="field">
        <label for="password">Password</label>
        <input type="password" id="password" required placeholder="••••••••" autocomplete="current-password">
      </div>
      <button type="submit" id="login-btn">Login &amp; link</button>
      <p class="hint"><a href="#" onclick="showRecover(event)">Forgot your password?</a></p>
    </form>

    <!-- Forgot password (via recovery email — no manual OTP) -->
    <form id="recover-form" onsubmit="recover(event)" style="display:none">
      <div class="field">
        <label for="recover-email">Email</label>
        <input type="email" id="recover-email" required placeholder="you@email.com" autocomplete="email">
      </div>
      <button type="submit" id="recover-btn">Send recovery email</button>
      <p class="hint"><a href="#" onclick="showLogin(event)">Back to login</a></p>
    </form>

    <!-- Email belum terverifikasi (non-blocking warning + resend) -->
    <div id="verify-warning" style="display:none">
      <div class="notice" id="verify-notice">
        Your email <strong id="verify-email"></strong> is not verified yet. You can still link the account, but please verify your email to secure it.
      </div>
      <div class="row">
        <button type="button" id="resend-btn" onclick="resendVerification(event)">Kirim ulang email verifikasi</button>
        <button type="button" id="continue-btn" class="secondary" onclick="confirmLink()">Lanjutkan tautkan</button>
      </div>
    </div>

    <!-- Success → auto-close tab -->
    <div id="success" class="success" style="display:none">
      <p>✅ Akun Telegram Anda berhasil ditautkan!</p>
      <p class="hint">Tab ini akan ditutup otomatis… Jika tidak tertutup, tutup secara manual.</p>
      <div class="row">
        <button type="button" class="secondary" onclick="tryClose()">Tutup tab ini</button>
      </div>
    </div>
  </div>
  <script>
    const SUPABASE_URL = "__SUPABASE_URL__";
    const SUPABASE_ANON_KEY = "__SUPABASE_ANON_KEY__";
    const LINK_TOKEN = "__TOKEN__";
    let email = "";
    let accessToken = null;
    const notice = document.getElementById("notice");

    function show(message, ok) {
      notice.textContent = message;
      notice.classList.toggle("ok", !!ok);
      notice.style.display = "block";
    }

    function hideAll() {
      document.getElementById("login-form").style.display = "none";
      document.getElementById("recover-form").style.display = "none";
      document.getElementById("verify-warning").style.display = "none";
      document.getElementById("success").style.display = "none";
    }

    function showLogin(e) {
      if (e) e.preventDefault();
      hideAll();
      notice.style.display = "none";
      document.getElementById("login-form").style.display = "block";
    }

    function showRecover(e) {
      e.preventDefault();
      hideAll();
      notice.style.display = "none";
      document.getElementById("recover-form").style.display = "block";
    }

    function tryClose() {
      try { window.close(); } catch (err) { /* blocked by browser — button stays */ }
    }

    async function login(event) {
      event.preventDefault();
      email = document.getElementById("email").value.trim();
      const password = document.getElementById("password").value;
      const btn = document.getElementById("login-btn");
      btn.disabled = true;
      btn.textContent = "Logging in…";
      try {
        const res = await fetch(SUPABASE_URL + "/auth/v1/token?grant_type=password", {
          method: "POST",
          headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ email: email, password: password })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok || !data.access_token) {
          const msg = data.error_description || data.msg || data.error || "Check your email and password.";
          show("Login failed: " + msg);
          return;
        }
        accessToken = data.access_token;
        // Email belum terverifikasi → warning non-blocking + opsi kirim ulang.
        if (data.user && !data.user.email_confirmed_at) {
          hideAll();
          document.getElementById("verify-email").textContent = email;
          document.getElementById("verify-warning").style.display = "block";
          notice.style.display = "none";
          return;
        }
        await confirmLink();
      } catch (err) {
        show("Network error — please try again.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Login";
      }
    }

    async function confirmLink() {
      try {
        const confirm = await fetch("/api/telegram/link/confirm", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ link_token: LINK_TOKEN, access_token: accessToken })
        });
        if (confirm.ok) {
          hideAll();
          document.getElementById("success").style.display = "block";
          setTimeout(tryClose, 1500); // auto-close tab after linking
        } else {
          const err = await confirm.json().catch(() => ({}));
          show("Could not link: " + (err.detail || "unknown error. The link may have expired — send /start again."));
          showLogin(null);
        }
      } catch (err) {
        show("Network error — please try again.");
        showLogin(null);
      }
    }

    async function recover(event) {
      event.preventDefault();
      const recoverEmail = document.getElementById("recover-email").value.trim();
      const btn = document.getElementById("recover-btn");
      btn.disabled = true;
      btn.textContent = "Sending…";
      try {
        const res = await fetch(SUPABASE_URL + "/auth/v1/recover", {
          method: "POST",
          headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ email: recoverEmail })
        });
        if (res.status === 429) { show("Too many requests — please wait a minute and try again."); return; }
        if (!res.ok) { show("Could not send the recovery email. Please check the address and try again."); return; }
        show("📧 Recovery email sent to " + recoverEmail + ". Follow the link in the email to set a new password, then log in above.", true);
      } catch (err) {
        show("Network error — please try again.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Send recovery email";
      }
    }

    async function resendVerification(event) {
      event.preventDefault();
      const btn = document.getElementById("resend-btn");
      btn.disabled = true;
      btn.textContent = "Sending…";
      try {
        const res = await fetch(SUPABASE_URL + "/auth/v1/resend", {
          method: "POST",
          headers: { "apikey": SUPABASE_ANON_KEY, "Content-Type": "application/json" },
          body: JSON.stringify({ type: "signup", email: email })
        });
        if (!res.ok) { show("Could not resend the verification email. Please try again."); return; }
        show("📧 Verification email sent to " + email + ". Check your inbox, then come back and click 'Lanjutkan tautkan'.", true);
      } catch (err) {
        show("Network error — please try again.");
      } finally {
        btn.disabled = false;
        btn.textContent = "Kirim ulang email verifikasi";
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
