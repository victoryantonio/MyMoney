"""
Telegram bot business logic.
Handles /start (account linking), /undo, /edit, /confirm, /cancel, photo
receipts (OCR via vision LLM), and natural language text logging.

Natural-language results (text + /edit) are saved DIRECTLY — no
/confirm confirmation gate (user decision, overrides pending-confirmation
flow previously described by REQUIREMENTS US-05/US-08). /undo remains
available to revert the most recent Telegram transaction.

Receipt photos use the same OCR concept as the Android camera menu
(Phase 6): merchant, line items (name/qty/price), date dd-mm-yyyy,
category (locked → "Other" when unknown), account (matched by name →
default account when absent).
"""

from datetime import datetime
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.nlu_parser import parse_text_to_transaction
from app.core.pending_service import cancel_pending_transaction, confirm_pending_transaction
from app.core.receipt_ocr import ParsedReceipt, parse_receipt_image
from app.core.report_service import get_report_summary, parse_period_arg, period_label
from app.core.security import create_telegram_link_token
from app.core.transaction_service import (
    create_transaction_internal,
    delete_transaction_internal,
    get_or_create_category,
    get_or_create_default_account,
    update_transaction_internal,
)
from app.models.account import Account
from app.models.profile import Profile
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction
from app.schemas.report import ReportSummaryResponse

log = structlog.get_logger()


def _format_report(summary: ReportSummaryResponse, label: str) -> str:
    """Render a period summary as a compact Telegram text message."""

    def fmt(v) -> str:
        return f"{v:,.0f}"

    lines = [
        f"📊 Report — {label}",
        f"📈 Income: IDR {fmt(summary.total_income)}",
        f"📉 Expense: IDR {fmt(summary.total_expense)}",
        f"Net: IDR {summary.net:+,.0f}",
    ]
    if summary.categories:
        lines.append("")
        lines.append("By Category:")
        for c in summary.categories:
            icon = "📈" if c.type == "income" else "📉"
            lines.append(f"{icon} {c.name}: {fmt(c.total)}")
    else:
        lines.append("")
        lines.append("No transactions in this period.")
    return "\n".join(lines)


async def _download_telegram_file(file_id: str) -> bytes | None:
    """Download a Telegram file (by file_id) as raw bytes via the Bot API."""
    api_base = f"https://api.telegram.org/bot{settings.telegram_bot_token}"
    file_base = f"https://api.telegram.org/file/bot{settings.telegram_bot_token}"
    timeout = httpx.Timeout(connect=15.0, read=90.0, write=30.0, pool=15.0)
    async with httpx.AsyncClient(timeout=timeout) as client:
        try:
            resp = await client.get(f"{api_base}/getFile", params={"file_id": file_id})
            resp.raise_for_status()
            data = resp.json()
            file_path = data["result"]["file_path"]
            # Telegram uses a separate /file/bot endpoint for binary content.
            file_resp = await client.get(f"{file_base}/{file_path}")
            file_resp.raise_for_status()
            return file_resp.content
        except Exception as e:  # noqa: BLE001 — gateway must degrade gracefully
            log.warning("telegram_file_download_failed", error=str(e), file_id=file_id)
            return None


def _find_account_by_name(db: Session, user_id: Any, account_name: str) -> Account | None:
    """Match a user's account by name (case-insensitive). Returns None if absent."""
    name = account_name.strip()
    if not name:
        return None
    return db.scalar(
        select(Account).where(
            Account.user_id == user_id,
            Account.is_active == True,  # noqa: E712
            Account.account_name.ilike(f"%{name}%"),
        )
    )


def _format_receipt_reply(parsed: ParsedReceipt, tx: Transaction) -> str:
    """Render a saved receipt transaction as a compact Telegram text message."""

    def fmt(v) -> str:
        return f"{v:,.0f}"

    icon = "📉" if tx.type == "expense" else "📈"
    lines = [
        f"Saved! {icon}",
        f"🏪 {parsed.merchant or tx.note or 'Receipt'}",
        f"💰 IDR {fmt(tx.total_amount)}",
    ]
    if tx.items:
        lines.append("")
        for item in tx.items:
            qty = f"{item.qty:g}".rstrip("0").rstrip(".") if item.qty % 1 else f"{item.qty:.0f}"
            lines.append(f"• {item.name} — {qty} x {fmt(item.price)}")
    if tx.note:
        lines.append("")
        lines.append(f"Note: {tx.note}")
    lines.append("")
    lines.append("Type /undo to revert.")
    return "\n".join(lines)


async def _handle_photo_message(db: Session, message: dict[str, Any], chat_id: int) -> str | None:
    """OCR a receipt photo, then save the transaction (same concept as Android)."""
    # The user MUST be linked first (same gate as text commands).
    link = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == chat_id))
    if not link or not link.user_id:
        return "Your account is not linked yet. Please type /start to link your account."

    photos = message.get("photo") or []
    if not photos:
        return None
    # Telegram sends several sizes — the last entry is the largest.
    file_id = photos[-1]["file_id"]

    image_bytes = await _download_telegram_file(file_id)
    if not image_bytes:
        return "I couldn't download your photo. Please try again."

    parsed = await parse_receipt_image(image_bytes)
    if parsed is None:
        return (
            "I couldn't read that nota. 😕\n"
            "Please make sure the photo is clear and well-lit, then try again.\n"
            "You can also type it manually, e.g. 'Mixue 2x21000'."
        )

    # ── Resolve category (locked for LLM paths — CODING_RULES §2.9.D) ────────
    category_name = parsed.category or "Other"
    category = get_or_create_category(
        db, link.user_id, category_name, parsed.type, allow_create=False
    )

    # ── Resolve account (match by name → default account when absent) ────────
    account = _find_account_by_name(db, link.user_id, parsed.account or "") or (
        get_or_create_default_account(db, link.user_id)
    )

    # ── Transaction date (dd-mm-yyyy from receipt, else now) ─────────────────
    tz_str = getattr(db.get(Profile, link.user_id), "timezone", None)
    tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
    if parsed.date:
        transaction_date = datetime.strptime(parsed.date, "%Y-%m-%d").replace(tzinfo=tz)
    else:
        transaction_date = datetime.now(tz)

    total = sum(item.line_total or item.qty * item.price for item in parsed.items)

    tx = create_transaction_internal(
        db=db,
        user_id=link.user_id,
        type=parsed.type,  # type: ignore
        total_amount=Decimal(str(total)),
        category_id=category.id,
        account_id=account.id,
        source="telegram",
        note=parsed.merchant,
        merchant=parsed.merchant,
        transaction_date=transaction_date,
        items=[item.model_dump() for item in parsed.items],
    )

    return _format_receipt_reply(parsed, tx)


async def process_telegram_update(db: Session, update: dict[str, Any]) -> str | None:
    """
    Process an incoming update from Telegram.
    Returns the exact string reply to send back to the user via Telegram API.
    If None is returned, no reply is sent (e.g. unsupported message types).
    """
    if "message" not in update:
        return None

    message = update["message"]
    chat_id = message["chat"]["id"]

    # ── 0. Photo receipts (OCR via vision LLM — same concept as Android) ────
    if "photo" in message:
        return await _handle_photo_message(db, message, chat_id)

    # Non-text messages (stickers, voice, etc.) are ignored.
    if "text" not in message:
        return None

    text = message["text"].strip()

    if not text:
        return "I can only process text or receipt photos. Try saying: 'Makan siang 35rb' or send a photo of your nota."

    # ── 1. Handle /start (Account Linking) ───────────────────────────────────
    if text.startswith("/start"):
        # Check if already linked
        link = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == chat_id))
        if link and link.user_id:
            user = db.get(Profile, link.user_id)
            if user:
                return f"Welcome back, {user.display_name}! Your account is already linked. Just type your expenses here (e.g. 'Coffee 25k')."

        # Generate link token
        token = create_telegram_link_token(chat_id)
        link_url = f"{settings.app_base_url.rstrip('/')}/api/telegram/link?token={token}"
        return (
            "Welcome to MyMoney! 💸\n\n"
            "To use this bot, please link your Telegram account to your MyMoney account by clicking the link below and logging in with your MyMoney email & password:\n\n"
            f"{link_url}\n\n"
            "(This link expires in 10 minutes)"
        )

    # For any other command/text, the user MUST be linked.
    link = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == chat_id))
    if not link or not link.user_id:
        return "Your account is not linked yet. Please type /start to link your account."

    user_id = link.user_id

    # ── 1.5 Handle /logout ───────────────────────────────────────────────────
    if text.startswith("/logout"):
        db.delete(link)
        db.commit()
        return (
            "Logged out. Your Telegram account is no longer linked to MyMoney.\n"
            "Send /start to link a different MyMoney account."
        )

    # ── 2. Handle /undo ──────────────────────────────────────────────────────
    if text.startswith("/undo"):
        # Find the most recent transaction created by this user via Telegram
        latest_tx = db.scalar(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.source == "telegram")
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        if not latest_tx:
            return "No recent Telegram transaction found to undo."

        amount_fmt = f"{latest_tx.total_amount:,.0f}"
        reply = f"Undid your last transaction:\n🗑️ {latest_tx.type.title()} - {amount_fmt} (Note: {latest_tx.note or 'none'})"
        delete_transaction_internal(db, latest_tx)
        return reply

    # ── 3. Handle /edit ──────────────────────────────────────────────────────
    if text.startswith("/edit"):
        # Format: /edit <new transaction text>
        # Example: /edit makan siang 50rb
        parts = text.split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /edit <new transaction details>\nExample: /edit makan siang 50rb"

        new_text = parts[1].strip()
        if not new_text:
            return "Please provide the new transaction details after /edit."

        # Find the most recent transaction created by this user via Telegram
        latest_tx = db.scalar(
            select(Transaction)
            .where(Transaction.user_id == user_id, Transaction.source == "telegram")
            .order_by(Transaction.created_at.desc())
            .limit(1)
        )
        if not latest_tx:
            return "No recent Telegram transaction found to edit."

        # Parse the new text → apply the edit DIRECTLY (no /confirm gate).
        parsed = await parse_text_to_transaction(new_text)
        if not parsed:
            return "I couldn't understand the new transaction. Please try again (e.g. '/edit makan siang 50rb')."

        # Category is locked for LLM paths (CODING_RULES §2.9.D) — unknown names
        # resolve to the default "Other" category instead of being auto-created.
        category = get_or_create_category(
            db, user_id, parsed.category, parsed.type, allow_create=False
        )

        items = [item.model_dump() for item in parsed.items] or None
        total = (
            Decimal(str(sum(item.line_total or item.qty * item.price for item in parsed.items)))
            if items
            else parsed.amount
        )

        updated = update_transaction_internal(
            db=db,
            transaction=latest_tx,
            type=parsed.type,  # type: ignore
            total_amount=total,
            category_id=category.id,
            note=parsed.note or new_text,
            merchant=parsed.merchant,
            items=items,
        )

        amount_fmt = f"{updated.total_amount:,.0f}"
        icon = "📉" if updated.type == "expense" else "📈"
        lines = [f"Edited! {icon}",
                 f"🏪 {parsed.merchant}" if parsed.merchant else None,
                 f"{category.name}: IDR {amount_fmt}"]
        if updated.items:
            lines.append("")
            for item in updated.items:
                qty = f"{item.qty:g}".rstrip("0").rstrip(".") if item.qty % 1 else f"{item.qty:.0f}"
                lines.append(f"• {item.name} — {qty} x {item.price:,.0f}")
        if updated.note:
            lines.append("")
            lines.append(f"Note: {updated.note}")
        return "\n".join(line for line in lines if line is not None)

    # ── 3.5 Handle /confirm and /cancel (pending confirmation) ────────────────
    if text.startswith("/confirm"):
        try:
            tx = confirm_pending_transaction(db, user_id)
        except ValueError as e:
            if "expired" in str(e):
                return "Your pending transaction has expired. Please type it again."
            return "No transaction is waiting for confirmation."
        amount_fmt = f"{tx.total_amount:,.0f}"
        icon = "📉" if tx.type == "expense" else "📈"
        cat_name = tx.category.name if tx.category else "Other"
        return f"Saved! {icon}\n{cat_name}: IDR {amount_fmt}\nNote: {tx.note or 'none'}"

    if text.startswith("/cancel"):
        try:
            cancel_pending_transaction(db, user_id)
        except ValueError as e:
            if "expired" in str(e):
                return "Your pending transaction has expired. Please type it again."
            return "No transaction is waiting for confirmation."
        return "Cancelled. Nothing was saved."

    # ── 3.6 Handle /report (US-17) ───────────────────────────────────────────
    if text.startswith("/report"):
        parts = text.split(maxsplit=1)
        arg = parts[1].strip() if len(parts) > 1 else ""
        # Resolve the user's timezone so "bulan ini" means *their* month.
        user = db.get(Profile, user_id)
        tz_str = getattr(user, "timezone", None) if user else None
        tz = ZoneInfo(tz_str) if tz_str else ZoneInfo("UTC")
        start, end = parse_period_arg(arg, tz)
        summary = get_report_summary(db, user_id, start_date=start, end_date=end)
        return _format_report(summary, period_label(arg))

    # ── 4. Handle Natural Language Transaction ───────────────────────────────
    # We call DeepSeek via the NLU parser and SAVE the result DIRECTLY.
    # No /confirm gate (user decision). Use /undo to revert.
    parsed = await parse_text_to_transaction(text)

    if not parsed:
        return "I couldn't understand that transaction. Please try again (e.g. 'Beli bensin 20rb')."

    # Locked categories for LLM paths (CODING_RULES §2.9.D): unknown names
    # resolve to the default "Other" category instead of being auto-created.
    category = get_or_create_category(db, user_id, parsed.category, parsed.type, allow_create=False)
    account = get_or_create_default_account(db, user_id)

    # Multi-item: total = sum of line totals; single amount used otherwise.
    items = [item.model_dump() for item in parsed.items] or None
    total = (
        Decimal(str(sum(item.line_total or item.qty * item.price for item in parsed.items)))
        if items
        else parsed.amount
    )

    tx = create_transaction_internal(
        db=db,
        user_id=user_id,
        type=parsed.type,  # type: ignore
        total_amount=total,
        category_id=category.id,
        account_id=account.id,
        source="telegram",
        note=parsed.note or text,  # use original text as note if LLM didn't extract one
        merchant=parsed.merchant,
        items=items,
    )

    amount_fmt = f"{tx.total_amount:,.0f}"
    icon = "📉" if tx.type == "expense" else "📈"
    lines = [f"Saved! {icon}", f"🏪 {parsed.merchant}" if parsed.merchant else None,
             f"{category.name}: IDR {amount_fmt}"]
    if tx.items:
        lines.append("")
        for item in tx.items:
            qty = f"{item.qty:g}".rstrip("0").rstrip(".") if item.qty % 1 else f"{item.qty:.0f}"
            lines.append(f"• {item.name} — {qty} x {item.price:,.0f}")
    if tx.note:
        lines.append("")
        lines.append(f"Note: {tx.note}")
    lines.append("")
    lines.append("Type /undo to revert.")
    return "\n".join(line for line in lines if line is not None)
