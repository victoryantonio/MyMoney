"""
Matching Mutasi REST endpoint — unggah bukti mutasi bank, cocokkan dengan
transaksi tercatat, sisanya masuk sebagai pending_transaction.

POST /api/mutations/match
  - multipart: `file` (gambar screenshot/foto aplikasi bank, CSV/teks, atau PDF
    e-statement bank — PDF digital dibaca dari layer teksnya, PDF hasil scan
    di-render halaman demi halaman lalu dibaca vision LLM, jumlah halaman
    tidak dibatasi)
  - form opsional: `account_id` (akun yang diunggah), `amount_tolerance`,
    `date_window_days`

Response `MutationMatchResponse`: ringkasan + daftar pasangan
(mutasi ↔ transaksi) + mutasi yang belum tercatat. Mutasi yang belum cocok
TIDAK langsung menjadi transaksi — dibuat sebagai `pending_transaction`
(CODING_RULES §2.4) yang menunggu konfirmasi user di menu Pending.

Auth: JWT Supabase + akun aktif. Rate limit 10/menit per IP karena memanggil
vision LLM (CODING_RULES §2.10).
"""

import uuid
from datetime import UTC
from decimal import Decimal, InvalidOperation
from zoneinfo import ZoneInfo

import structlog
from fastapi import APIRouter, Depends, File, Form, HTTPException, Request, UploadFile, status
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_active_user
from app.core.mutation_matcher import (
    DEFAULT_AMOUNT_TOLERANCE,
    DEFAULT_DATE_WINDOW_DAYS,
    MatchPair,
    MutationPeriod,
    ParsedMutation,
    detect_statement_period,
    fallback_category_id,
    find_matches,
    is_pdf_upload,
    mutation_local_datetime,
    parse_mutation_image,
    parse_mutation_pdf,
    parse_mutation_text,
    resolve_upload_account,
)
from app.core.pending_service import (
    create_pending_transaction,
    purge_expired_pendings,
    purge_matching_pendings,
)
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.account import Account
from app.models.profile import Profile

log = structlog.get_logger()
router = APIRouter(prefix="/api/mutations", tags=["Matching Mutasi"])

# 20 MB — screenshot mutasi jauh lebih kecil, tetapi e-statement PDF beberapa
# halaman bisa besar. Batas ini dijaga agar memori container tetap aman.
MAX_UPLOAD_BYTES = 20 * 1024 * 1024


class MutationMatchResponse(BaseModel):
    """Hasil Matching Mutasi satu unggahan."""

    account_id: str | None = None
    account_name: str | None = None
    source_description: str | None = Field(
        default=None, description="Hint akun yang terbaca dari statement"
    )
    period: MutationPeriod | None = Field(
        default=None,
        description=(
            "Bulan yang dicakup berkas mutasi (dasar filter transaksi). "
            "null bila tidak ada tanggal yang terbaca."
        ),
    )
    total_mutations: int
    matched_count: int
    unmatched_mutation_count: int
    unmatched_transaction_count: int
    matches: list[MatchPair]
    unmatched_mutations: list[ParsedMutation]
    created_pending_ids: list[str]


@router.post("/match", response_model=MutationMatchResponse)
@limiter.limit("10/minute")
async def match_mutations(
    request: Request,
    file: UploadFile = File(...),
    account_id: uuid.UUID | None = Form(default=None),
    amount_tolerance: str | None = Form(default=None),
    date_window_days: int | None = Form(default=None),
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> MutationMatchResponse:
    """
    Cocokkan satu unggahan mutasi bank dengan transaksi yang sudah tercatat.

    Baris mutasi yang belum ada di sistem dibuat sebagai `pending_transaction`
    (bukan transaksi nyata) agar user mengonfirmasi dulu.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Empty file")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail="File terlalu besar (maks 20 MB)",
        )

    tolerance = _parse_tolerance(amount_tolerance)
    window = max(0, min(date_window_days or DEFAULT_DATE_WINDOW_DAYS, 30))

    filename = (file.filename or "").lower()
    content_type = (file.content_type or "").lower()
    is_text = content_type.startswith(("text/", "application/csv")) or filename.endswith(
        (".csv", ".txt", ".tsv")
    )

    if is_text:
        try:
            extraction = await parse_mutation_text(raw.decode("utf-8", errors="replace"))
        except UnicodeDecodeError:
            extraction = None
    elif is_pdf_upload(raw, mime_type=content_type, filename=filename):
        extraction = await parse_mutation_pdf(raw)
    else:
        if not content_type.startswith("image/") and not filename.endswith(
            (".jpg", ".jpeg", ".png", ".webp", ".heic", ".heif")
        ):
            raise HTTPException(
                status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
                detail=(
                    "Format tidak didukung. Unggah screenshot/foto mutasi bank "
                    "(JPG/PNG/WebP), PDF e-statement, atau ekspor CSV."
                ),
            )
        mime = content_type if content_type.startswith("image/") else "image/jpeg"
        extraction = await parse_mutation_image(raw, mime)

    if extraction is None:
        log.warning(
            "mutation_match_unrecognized",
            user_id=str(current_user.id),
            filename=file.filename,
        )
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=(
                "Mutasi tidak terbaca — pastikan berkas memuat daftar transaksi "
                "(tanggal, keterangan, nominal) lalu coba lagi."
            ),
        )

    # Akun target: pilihan user → hint dari statement → None (semua akun).
    resolved_account_id = resolve_upload_account(
        db,
        user_id=current_user.id,
        account_id=account_id,
        account_hint=extraction.account_hint,
    )
    account: Account | None = None
    if resolved_account_id is not None:
        account = db.scalars(
            select(Account).where(
                Account.id == resolved_account_id,
                Account.user_id == current_user.id,
            )
        ).first()

    # Periode = bulan yang dicakup berkas (mis. September 2026). Dasar filter
    # transaksi: hanya bulan itu (+ akun terpilih) yang ikut dicocokkan, bukan
    # seluruh riwayat user.
    period = detect_statement_period(extraction.mutations)
    tz = _user_timezone(current_user)

    matches, unmatched, unmatched_txs = find_matches(
        db,
        user_id=current_user.id,
        mutations=extraction.mutations,
        account_id=resolved_account_id,
        amount_tolerance=tolerance,
        date_window_days=window,
        period=period,
        tz=tz,
    )

    # Bersihkan sisa pending dari unggahan sebelumnya yang tidak pernah
    # dikonfirmasi user + pending yang sudah kedaluwarsa. Unggahan baru
    # menggantikan daftar lama, jadi tabel pending tidak menumpuk baris mati.
    # Dilakukan SEBELUM membuat pending baru dan hanya setelah berkas berhasil
    # dibaca, agar unggahan gagal tidak menghapus pending yang masih berlaku.
    purge_expired_pendings(db, current_user.id)
    purge_matching_pendings(db, current_user.id)

    pending_ids = _create_pendings(
        db,
        current_user=current_user,
        mutations=unmatched,
        account_id=resolved_account_id,
        source_label=extraction.account_hint or (file.filename or "mutasi bank"),
        tz=tz,
    )
    db.commit()

    log.info(
        "mutation_match_ok",
        user_id=str(current_user.id),
        total=len(extraction.mutations),
        matched=len(matches),
        unmatched=len(unmatched),
        pendings=len(pending_ids),
        period=period.label if period else None,
    )

    return MutationMatchResponse(
        account_id=str(resolved_account_id) if resolved_account_id else None,
        account_name=account.account_name if account else None,
        source_description=extraction.account_hint,
        period=period,
        total_mutations=len(extraction.mutations),
        matched_count=len(matches),
        unmatched_mutation_count=len(unmatched),
        unmatched_transaction_count=len(unmatched_txs),
        matches=matches,
        unmatched_mutations=unmatched,
        created_pending_ids=[str(pid) for pid in pending_ids],
    )


def _user_timezone(profile: Profile) -> ZoneInfo:
    """Zona waktu profil user (fallback Asia/Jakarta bila tidak valid)."""
    name = (profile.timezone or "").strip() or "Asia/Jakarta"
    try:
        return ZoneInfo(name)
    except Exception:  # noqa: BLE001 - nama zona rusak tidak boleh menggagalkan unggahan
        log.warning("mutation_invalid_timezone", timezone=name)
        return ZoneInfo("Asia/Jakarta")


def _parse_tolerance(value: str | None) -> Decimal:
    if value is None or not value.strip():
        return DEFAULT_AMOUNT_TOLERANCE
    try:
        tolerance = Decimal(value.strip())
    except InvalidOperation:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="amount_tolerance harus berupa angka",
        ) from None
    if tolerance < 0 or tolerance > Decimal("100000"):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="amount_tolerance harus antara 0 dan 100000",
        )
    return tolerance


def _create_pendings(
    db: Session,
    *,
    current_user: Profile,
    mutations: list[ParsedMutation],
    account_id: uuid.UUID | None,
    source_label: str,
    tz: ZoneInfo,
) -> list[uuid.UUID]:
    """Buat pending_transaction untuk mutasi yang belum tercatat di sistem."""
    created: list[uuid.UUID] = []
    for mutation in mutations:
        tx_type = "expense" if mutation.direction == "debit" else "income"
        try:
            category_id = fallback_category_id(db, current_user.id, tx_type)
        except ValueError:
            log.error(
                "mutation_match_no_category",
                user_id=str(current_user.id),
                type=tx_type,
            )
            break

        note = f"Mutasi: {mutation.description}"
        if mutation.date:
            note += f" ({mutation.date}"
            note += f" {mutation.time})" if mutation.time else ")"

        # Tanggal+jam ASLI dari mutasi. Disimpan terpisah dari `note` supaya
        # saat user konfirmasi, transaksi tercatat pada waktu terjadinya
        # transaksi di bank — bukan pada waktu konfirmasi (bug lama).
        local_dt = mutation_local_datetime(mutation, tz)
        transaction_date = local_dt.astimezone(UTC) if local_dt else None

        pending = create_pending_transaction(
            db,
            user_id=current_user.id,
            type=tx_type,
            total_amount=mutation.amount,
            category_id=category_id,
            source="app",
            note=note,
            merchant=mutation.description[:150],
            account_id=account_id,
            confidence="medium",
            raw_input=f"Matching Mutasi — {source_label}",
            transaction_date=transaction_date,
            timezone=tz.key,
            expires_minutes=60 * 24,  # 1 hari: user perlu waktu memeriksa
        )
        created.append(pending.id)
    return created
