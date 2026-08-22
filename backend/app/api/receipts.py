"""
receipts.py — upload receipt photo for OCR parsing (US-07 to US-10).
Returns parsed result for user review — NOT auto-committed (pending confirmation pattern).
"""
import uuid
from datetime import datetime, timezone
from pathlib import Path

import aiofiles
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_dep
from app.core.receipt_service import parse_receipt_image, ReceiptParseError
from app.core.config import settings
from app.db.session import get_db
from app.models.models import User

router = APIRouter(prefix="/receipts", tags=["Receipts"])

ALLOWED_CONTENT_TYPES = {"image/jpeg", "image/png", "image/webp"}
MAX_FILE_SIZE_MB = 10


@router.post("/parse")
async def parse_receipt(
    file: UploadFile = File(...),
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Upload receipt photo and return parsed transaction data for review.
    Does NOT commit to DB — caller must confirm and POST to /transactions.
    Low confidence is flagged but not blocked (US-09).
    """
    if file.content_type not in ALLOWED_CONTENT_TYPES:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail=f"Format file tidak didukung. Gunakan JPEG, PNG, atau WebP.",
        )

    image_bytes = await file.read()

    if len(image_bytes) > MAX_FILE_SIZE_MB * 1024 * 1024:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail=f"File terlalu besar. Maksimal {MAX_FILE_SIZE_MB}MB.",
        )

    try:
        parsed = await parse_receipt_image(image_bytes, mime_type=file.content_type)
    except ReceiptParseError as exc:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(exc))

    # Save original image to receipts dir (US-10: keep original for reference)
    receipt_filename = f"{uuid.uuid4()}.jpg"
    receipts_path = Path(settings.RECEIPTS_DIR)
    receipts_path.mkdir(parents=True, exist_ok=True)
    async with aiofiles.open(receipts_path / receipt_filename, "wb") as f:
        await f.write(image_bytes)

    return {
        "parsed": {
            "merchant": parsed.merchant,
            "date": parsed.date,
            "total": float(parsed.total),
            "items": [{"name": i.name, "qty": float(i.qty), "price": float(i.price)} for i in parsed.items],
            "confidence": parsed.confidence,
        },
        "receipt_image_path": str(receipts_path / receipt_filename),
        "review_required": parsed.confidence == "low",
    }
