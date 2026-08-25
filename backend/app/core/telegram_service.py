"""
Telegram bot business logic.
Handles /start (account linking), /undo, /edit, /confirm, /cancel, and
natural language text logging.

Natural-language results (text + /edit) are saved DIRECTLY — no
/confirm confirmation gate (user decision, overrides pending-confirmation
flow previously described by REQUIREMENTS US-05/US-08). /undo remains
available to revert the most recent Telegram transaction.
"""

from typing import Any
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.nlu_parser import parse_text_to_transaction
from app.core.pending_service import cancel_pending_transaction, confirm_pending_transaction
from app.core.report_service import get_report_summary, parse_period_arg, period_label
from app.core.security import create_telegram_link_token
from app.core.transaction_service import (
    create_transaction_internal,
    delete_transaction_internal,
    get_or_create_category,
    get_or_create_default_account,
    update_transaction_internal,
)
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction
from app.models.user import User
from app.schemas.report import ReportSummaryResponse


def _format_report(summary: ReportSummaryResponse, label: str) -> str:
    """Render a period summary as a compact Telegram text message."""

    def fmt(v) -> str:
        return f"{v:,.0f}"

    lines = [
        f"📊 Report — {label}",
        f"📈 Income: {fmt(summary.total_income)} IDR",
        f"📉 Expense: {fmt(summary.total_expense)} IDR",
        f"Net: {summary.net:+,.0f} IDR",
    ]
    if summary.categories:
        lines.append("")
        lines.append("By category:")
        for c in summary.categories:
            icon = "📈" if c.type == "income" else "📉"
            lines.append(f"{icon} {c.name}: {fmt(c.total)} IDR")
    else:
        lines.append("")
        lines.append("No transactions in this period.")
    return "\n".join(lines)


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

    # Check if message has text field (non-text messages like photos don't)
    if "text" not in message:
        return None

    text = message["text"].strip()

    if not text:
        return "I can only process text messages right now. Try saying: 'Makan siang 35rb'."

    # ── 1. Handle /start (Account Linking) ───────────────────────────────────
    if text.startswith("/start"):
        # Check if already linked
        link = db.scalar(select(TelegramLink).where(TelegramLink.telegram_id == chat_id))
        if link and link.user_id:
            user = db.get(User, link.user_id)
            if user:
                return f"Welcome back, {user.display_name}! Your account is already linked. Just type your expenses here (e.g. 'Coffee 25k')."

        # Generate link token
        token = create_telegram_link_token(chat_id)
        link_url = f"{settings.app_base_url}/api/telegram/link?token={token}"
        return (
            "Welcome to MyMoney! 💸\n\n"
            "To use this bot, please link your Telegram account to your MyMoney account by clicking the link below:\n\n"
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

        updated = update_transaction_internal(
            db=db,
            transaction=latest_tx,
            type=parsed.type,  # type: ignore
            total_amount=parsed.amount,
            category_id=category.id,
            note=parsed.note or new_text,
        )

        amount_fmt = f"{updated.total_amount:,.0f}"
        icon = "📉" if updated.type == "expense" else "📈"
        return (
            f"Edited! {icon}\n"
            f"{category.name}: {amount_fmt} IDR\n"
            f"Note: {updated.note or 'none'}"
        )

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
        return f"Saved! {icon}\n{cat_name}: {amount_fmt} IDR\nNote: {tx.note or 'none'}"

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
        user = db.get(User, user_id)
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

    tx = create_transaction_internal(
        db=db,
        user_id=user_id,
        type=parsed.type,  # type: ignore
        total_amount=parsed.amount,
        category_id=category.id,
        account_id=account.id,
        source="telegram",
        note=parsed.note or text,  # use original text as note if LLM didn't extract one
    )

    amount_fmt = f"{tx.total_amount:,.0f}"
    icon = "📉" if tx.type == "expense" else "📈"
    return (
        f"Saved! {icon}\n"
        f"{category.name}: {amount_fmt} IDR\n"
        f"Note: {tx.note or 'none'}\n\n"
        "Type /undo to revert."
    )
