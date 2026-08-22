"""
telegram_webhook.py — handles all incoming Telegram messages and commands.

Rules per ARCHITECTURE.md §3.2 and CODING_RULES.md §2.2:
- This API layer calls service layer ONLY. No business logic here.
- telegram_user_id → user_id mapping done via TelegramLink.
- Pending confirmation state stored in-memory (dict) per user session.
  (Simple enough for v1 solo use — a Redis store would be Fase v2 only if needed.)
- Commands: /start, /report, /batal <id>, /edit <id>
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone, timedelta
from typing import Any

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core import transaction_service, report_service
from app.core.nlu_parser import parse_text, ParseError
from app.core.config import settings
from app.db.session import get_db
from app.models.models import TelegramLink, User
from app.schemas.schemas import TransactionCreateRequest, TransactionItemRequest

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/webhook", tags=["Webhook"])

# In-memory pending confirmations: {telegram_id: parsed_transaction_data}
# Simple dict sufficient for personal v1 use (not multi-user scale).
_pending: dict[int, dict[str, Any]] = {}


async def _get_user_from_telegram(db: AsyncSession, telegram_id: int) -> User | None:
    result = await db.execute(
        select(User)
        .join(TelegramLink, TelegramLink.user_id == User.id)
        .where(TelegramLink.telegram_id == telegram_id)
    )
    return result.scalar_one_or_none()


async def _send_message(chat_id: int, text: str) -> None:
    """Send a reply to the user via Telegram Bot API."""
    import httpx
    async with httpx.AsyncClient(timeout=10.0) as client:
        await client.post(
            f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/sendMessage",
            json={"chat_id": chat_id, "text": text, "parse_mode": "Markdown"},
        )


@router.post("/telegram")
async def telegram_webhook(request: Request, db: AsyncSession = Depends(get_db)) -> dict:
    """
    Main Telegram webhook endpoint.
    Receives all updates from Telegram and dispatches to handlers.
    """
    # Verify webhook secret (simple header check — sufficient for v1)
    secret = request.headers.get("X-Telegram-Bot-Api-Secret-Token")
    if secret != settings.TELEGRAM_WEBHOOK_SECRET:
        raise HTTPException(status_code=403, detail="Invalid webhook secret")

    body = await request.json()
    message = body.get("message") or body.get("edited_message")
    if not message:
        return {"ok": True}

    chat_id: int = message["chat"]["id"]
    telegram_id: int = message["from"]["id"]
    text: str = message.get("text", "").strip()
    photo = message.get("photo")

    # Dispatch
    if text.startswith("/start"):
        await _handle_start(db, telegram_id, chat_id, text)
    elif text.startswith("/report"):
        await _handle_report(db, telegram_id, chat_id, text)
    elif text.startswith("/batal"):
        await _handle_batal(db, telegram_id, chat_id, text)
    elif text.lower() in ("ya", "y", "ok", "iya", "yes", "konfirmasi"):
        await _handle_confirmation(db, telegram_id, chat_id)
    elif text.lower() in ("tidak", "batal", "cancel", "no"):
        _pending.pop(telegram_id, None)
        await _send_message(chat_id, "Dibatalkan.")
    elif photo:
        await _handle_photo(db, telegram_id, chat_id, message)
    elif text:
        await _handle_text(db, telegram_id, chat_id, text)

    return {"ok": True}


async def _handle_start(db: AsyncSession, telegram_id: int, chat_id: int, text: str) -> None:
    """Link Telegram account to MyMoney user via /start <link_token> — or just greet."""
    # For v1: simple greeting. Proper link-token flow can be added later.
    existing_user = await _get_user_from_telegram(db, telegram_id)
    if existing_user:
        await _send_message(chat_id, f"Halo {existing_user.display_name}! Akun sudah terhubung.")
    else:
        await _send_message(
            chat_id,
            "Halo! Akun Telegram kamu belum terhubung ke MyMoney.\n"
            "Buka app dan hubungkan akun Telegram dari menu Pengaturan.",
        )


async def _handle_report(db: AsyncSession, telegram_id: int, chat_id: int, text: str) -> None:
    """Handle /report [bulan-ini|minggu-ini|hari-ini]."""
    user = await _get_user_from_telegram(db, telegram_id)
    if not user:
        await _send_message(chat_id, "Akun belum terhubung. Buka app MyMoney dulu.")
        return

    now = datetime.now(timezone.utc)
    if "minggu" in text:
        date_from = now - timedelta(days=7)
    elif "hari" in text:
        date_from = now.replace(hour=0, minute=0, second=0, microsecond=0)
    else:
        # Default: current month
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)

    summary = await report_service.get_summary(db, user.id, date_from, now)
    reply = report_service.format_report_text(summary)
    await _send_message(chat_id, f"```\n{reply}\n```")


async def _handle_batal(db: AsyncSession, telegram_id: int, chat_id: int, text: str) -> None:
    """Handle /batal <tx_id> — delete a transaction."""
    user = await _get_user_from_telegram(db, telegram_id)
    if not user:
        await _send_message(chat_id, "Akun belum terhubung.")
        return

    parts = text.split()
    if len(parts) < 2:
        await _send_message(chat_id, "Format: /batal <id-transaksi>")
        return

    try:
        tx_id = uuid.UUID(parts[1])
    except ValueError:
        await _send_message(chat_id, "ID transaksi tidak valid.")
        return

    try:
        await transaction_service.delete_transaction(db, user.id, tx_id, source="telegram")
        await _send_message(chat_id, "Transaksi dihapus.")
    except ValueError as exc:
        await _send_message(chat_id, str(exc))


async def _handle_text(db: AsyncSession, telegram_id: int, chat_id: int, text: str) -> None:
    """Parse free-form text via GLM 5.2 and send confirmation prompt."""
    user = await _get_user_from_telegram(db, telegram_id)
    if not user:
        await _send_message(chat_id, "Akun belum terhubung. Buka app MyMoney dulu.")
        return

    try:
        parsed = await parse_text(text)
    except ParseError as exc:
        await _send_message(chat_id, str(exc))
        return

    # Store pending — awaiting user confirmation (US-05)
    _pending[telegram_id] = {
        "user_id": user.id,
        "parsed": parsed,
        "raw_text": text,
    }

    type_label = "Pemasukan" if parsed.type == "income" else "Pengeluaran"
    merchant_str = f" — {parsed.merchant}" if parsed.merchant else ""
    await _send_message(
        chat_id,
        f"*{type_label}*{merchant_str}\n"
        f"Nominal: Rp{parsed.amount:,.0f}\n"
        f"Kategori: {parsed.category}\n\n"
        f"Simpan? (ya/tidak)",
    )


async def _handle_confirmation(db: AsyncSession, telegram_id: int, chat_id: int) -> None:
    """Commit pending transaction after user confirms."""
    pending = _pending.pop(telegram_id, None)
    if not pending:
        await _send_message(chat_id, "Tidak ada transaksi yang menunggu konfirmasi.")
        return

    user_id: uuid.UUID = pending["user_id"]
    
    is_receipt = "parsed_receipt" in pending
    if is_receipt:
        parsed = pending["parsed_receipt"]
        cat_name = "Kebutuhan" # Default category for receipts
        tx_type = "expense"
        merchant = parsed.merchant
        amount = parsed.total
        note = f"Dari nota {parsed.date or ''}".strip()
        account_hint = None
        confidence = parsed.confidence
        receipt_image_path = pending.get("receipt_image_path")
        items = [TransactionItemRequest(name=i.name, qty=i.qty, price=i.price) for i in parsed.items]
    else:
        parsed = pending["parsed"]
        cat_name = parsed.category
        tx_type = parsed.type
        merchant = parsed.merchant
        amount = parsed.amount
        note = parsed.note
        account_hint = parsed.account_hint
        confidence = "high"
        receipt_image_path = None
        items = []

    # Resolve category_id from name — find matching default category
    from sqlalchemy import select as sql_select
    from app.models.models import Category, Account

    cat_result = await db.execute(
        sql_select(Category).where(
            (Category.user_id == user_id) | (Category.user_id == None),
            Category.name == parsed.category,
        )
    )
    category = cat_result.scalars().first()
    if not category:
        # Fallback to "Lainnya"
        cat_result = await db.execute(
            sql_select(Category).where(
                Category.user_id == None, Category.name == "Lainnya", Category.type == tx_type
            )
        )
        category = cat_result.scalar_one_or_none()

    if not category:
        await _send_message(chat_id, "Kategori tidak ditemukan. Coba input manual dari app.")
        return

    # Use first active account, or detect from account_hint
    acc_query = sql_select(Account).where(Account.user_id == user_id, Account.is_active == True)
    if account_hint:
        acc_result = await db.execute(
            acc_query.where(Account.account_name.ilike(f"%{account_hint}%"))
        )
        account = acc_result.scalars().first()
    else:
        account = None

    if not account:
        acc_result = await db.execute(acc_query.order_by(Account.created_at.asc()))
        account = acc_result.scalars().first()

    if not account:
        await _send_message(chat_id, "Tidak ada akun aktif. Tambah akun dari app dulu.")
        return

    payload = TransactionCreateRequest(
        type=tx_type,
        total_amount=amount,
        category_id=category.id,
        account_id=account.id,
        merchant=merchant,
        note=note,
        transaction_date=datetime.now(timezone.utc),
        items=items,
    )

    try:
        tx = await transaction_service.create_transaction(
            db, user_id, payload, source="telegram", confidence=confidence, receipt_image_url=receipt_image_path
        )
        type_label = "Pemasukan" if tx.type == "income" else "Pengeluaran"
        await _send_message(
            chat_id,
            f"Tercatat: Rp{tx.total_amount:,.0f} — {tx.category.name}",
        )
    except ValueError as exc:
        await _send_message(chat_id, str(exc))


async def _handle_photo(db: AsyncSession, telegram_id: int, chat_id: int, message: dict) -> None:
    """Forward receipt photo to receipt_service for OCR parsing."""
    from app.core.receipt_service import parse_receipt_image, ReceiptParseError
    import httpx
    import aiofiles
    from pathlib import Path

    user = await _get_user_from_telegram(db, telegram_id)
    if not user:
        await _send_message(chat_id, "Akun belum terhubung. Buka app MyMoney dulu.")
        return

    await _send_message(chat_id, "Membaca nota...")

    # Get the highest-resolution photo
    photos = message["photo"]
    file_id = photos[-1]["file_id"]

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            file_resp = await client.get(
                f"https://api.telegram.org/bot{settings.TELEGRAM_BOT_TOKEN}/getFile",
                params={"file_id": file_id},
            )
            file_path = file_resp.json()["result"]["file_path"]
            img_resp = await client.get(
                f"https://api.telegram.org/file/bot{settings.TELEGRAM_BOT_TOKEN}/{file_path}"
            )
            image_bytes = img_resp.content
    except Exception as exc:
        logger.error("telegram_photo_download_failed", error=str(exc))
        await _send_message(chat_id, "Gagal mengunduh foto. Coba lagi.")
        return

    try:
        parsed = await parse_receipt_image(image_bytes)
    except ReceiptParseError as exc:
        await _send_message(chat_id, str(exc))
        return

    confidence_note = ""
    if parsed.confidence == "low":
        confidence_note = "\n⚠️ _Confidence rendah — periksa ulang sebelum konfirmasi._"

    items_text = ""
    if parsed.items:
        items_text = "\n\nRincian item:\n" + "\n".join(
            f"  {item.name} x{item.qty} @ Rp{item.price:,.0f}" for item in parsed.items
        )

    # Save original image to receipts dir
    receipt_filename = f"{uuid.uuid4()}.jpg"
    receipts_path = Path(settings.RECEIPTS_DIR)
    receipts_path.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(receipts_path / receipt_filename, "wb") as f:
        await f.write(image_bytes)

    _pending[telegram_id] = {
        "user_id": user.id,
        "parsed_receipt": parsed,
        "receipt_image_path": str(receipts_path / receipt_filename)
    }

    merchant_str = parsed.merchant or "(tidak diketahui)"
    await _send_message(
        chat_id,
        f"*Nota: {merchant_str}*\n"
        f"Total: Rp{parsed.total:,.0f}\n"
        f"Tanggal: {parsed.date or 'tidak diketahui'}"
        f"{items_text}"
        f"{confidence_note}\n\n"
        f"Simpan? (ya/tidak)",
    )
