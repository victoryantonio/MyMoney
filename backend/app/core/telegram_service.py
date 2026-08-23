"""
Telegram bot business logic.
Handles /start (account linking), /undo, /edit, and natural language text logging.
"""

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.nlu_parser import parse_text_to_transaction
from app.core.security import create_telegram_link_token
from app.core.transaction_service import (
    create_transaction_internal,
    get_or_create_category,
    get_or_create_default_account,
    update_transaction_internal,
)
from app.models.telegram_link import TelegramLink
from app.models.transaction import Transaction
from app.models.user import User


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
        link = db.scalar(
            select(TelegramLink).where(TelegramLink.telegram_id == chat_id)
        )
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
        db.delete(latest_tx)
        db.commit()
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

        # Parse the new text
        parsed = await parse_text_to_transaction(new_text)
        if not parsed:
            return "I couldn't understand the new transaction. Please try again (e.g. '/edit makan siang 50rb')."

        # Get or create category for the new type
        category = get_or_create_category(db, user_id, parsed.category, parsed.type)

        # Update the transaction
        updated_tx = update_transaction_internal(
            db=db,
            transaction=latest_tx,
            type=parsed.type,  # type: ignore
            total_amount=parsed.amount,
            category_id=category.id,
            note=parsed.note or new_text,
        )

        amount_fmt = f"{updated_tx.total_amount:,.0f}"
        icon = "📉" if updated_tx.type == "expense" else "📈"
        return f"Updated! {icon}\n{category.name}: {amount_fmt} IDR\nNote: {updated_tx.note}"

    # ── 4. Handle Natural Language Transaction ───────────────────────────────
    # We call OpenRouter via the NLU parser
    parsed = await parse_text_to_transaction(text)

    if not parsed:
        return "I couldn't understand that transaction. Please try again (e.g. 'Beli bensin 20rb')."

    account = get_or_create_default_account(db, user_id)
    category = get_or_create_category(db, user_id, parsed.category, parsed.type)

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
    return f"Saved! {icon}\n{category.name}: {amount_fmt} IDR\nNote: {tx.note}"
