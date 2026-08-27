"""
Receipt OCR REST endpoint — dipakai app Flutter (fitur "Scan Nota",
REQUIREMENTS US-07..US-10).

Alur sama dengan jalur foto Telegram: bytes gambar → `parse_receipt_image()`
(vision LLM DeepSeek) → `ParsedReceipt` terstruktur. Bedanya, hasil
dikembalikan ke client untuk direview/diedit (US-08) sebelum transaksi
disimpan via `POST /api/transactions` — bukan langsung disimpan.

Auth: JWT Supabase + akun aktif (sama seperti endpoint data lain).
Rate limit: 10/menit per IP (CODING_RULES §2.10 — endpoint ini memicu
panggilan LLM yang mahal/lambat).
"""

import structlog
from fastapi import APIRouter, Depends, File, HTTPException, Request, UploadFile, status
from sqlalchemy.orm import Session

from app.api.deps import require_active_user
from app.core.rate_limit import limiter
from app.core.receipt_ocr import ParsedReceipt, parse_receipt_image
from app.db.session import get_db
from app.models.profile import Profile

log = structlog.get_logger()
router = APIRouter(prefix="/api/receipts", tags=["Receipts"])

# 10 MB — batas wajar untuk foto nota; foto lebih besar ditolak lebih awal
# daripada membebani LLM.
MAX_IMAGE_BYTES = 10 * 1024 * 1024


@router.post("/ocr", response_model=ParsedReceipt)
@limiter.limit("10/minute")
async def ocr_receipt(
    request: Request,
    file: UploadFile = File(...),
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> ParsedReceipt:
    """
    Parse satu foto nota menjadi transaksi terstruktur.

    Response: `ParsedReceipt` (type, merchant, date, category, account, items).
    Error 422 bila foto tidak terbaca / bukan nota — client menampilkan pesan
    untuk memotret ulang atau input manual.
    """
    image_bytes = await file.read()
    if not image_bytes:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file")
    if len(image_bytes) > MAX_IMAGE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="Image too large (max 10 MB)",
        )

    parsed = await parse_receipt_image(image_bytes)
    if parsed is None:
        log.warning(
            "receipt_ocr_unrecognized",
            user_id=str(current_user.id),
            filename=file.filename,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Receipt not recognized — please retake the photo or enter the transaction manually",
        )

    log.info(
        "receipt_ocr_ok",
        user_id=str(current_user.id),
        filename=file.filename,
        merchant=parsed.merchant,
        items=len(parsed.items),
    )
    return parsed
