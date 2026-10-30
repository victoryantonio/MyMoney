"""
Pending confirmation API — dipakai layar "Matching" di app Flutter.

Latar belakang: fitur "Matching Mutasi" (Req 9) TIDAK pernah menyimpan baris
mutasi yang belum cocok sebagai transaksi nyata (CODING_RULES §2.4). Baris itu
masuk `pending_transactions` menunggu konfirmasi user. Sampai versi ini belum
ada endpoint maupun layar untuk melihat/menyelesaikan pending, sehingga user
mendapat pesan "buka menu Pending" padahal menunya tidak ada. Router ini
menutup celah tersebut.

Endpoint:
  GET  /api/pending                — daftar pending aktif (belum kedaluwarsa)
  GET  /api/pending/count          — jumlah pending aktif (badge tombol)
  POST /api/pending/{id}/confirm   — jadikan transaksi nyata (audited)
  POST /api/pending/{id}/cancel    — buang pending, tidak menyimpan apa pun

Semua endpoint hanya menyentuh baris milik user yang sedang login.
"""

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import require_active_user
from app.core.pending_service import (
    cancel_pending_transaction,
    confirm_pending_transaction,
    purge_expired_pendings,
)
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.account import Account
from app.models.pending_transaction import PendingTransaction
from app.models.profile import Profile
from app.schemas.pending import (
    PendingCancelResponse,
    PendingConfirmResponse,
    PendingCountResponse,
    PendingListResponse,
    PendingTransactionResponse,
)

log = structlog.get_logger()
router = APIRouter(prefix="/api/pending", tags=["Pending"])

MAX_LIST_ITEMS = 200


def _active_pending_filter(user_id: uuid.UUID):
    """Filter SQL: milik user & belum kedaluwarsa."""
    now = datetime.now(UTC)
    return (
        PendingTransaction.user_id == user_id,
        (PendingTransaction.expires_at.is_(None)) | (PendingTransaction.expires_at > now),
    )


def _to_response(
    pending: PendingTransaction,
    account_names: dict[uuid.UUID, str],
) -> PendingTransactionResponse:
    """Bangun DTO dengan nama kategori/akun yang sudah di-resolve."""
    category_name = pending.category.name if pending.category is not None else None
    account_name = account_names.get(pending.account_id) if pending.account_id is not None else None
    return PendingTransactionResponse(
        id=pending.id,
        action=pending.action,
        type=pending.type,
        total_amount=pending.total_amount,
        category_id=pending.category_id,
        category_name=category_name,
        account_id=pending.account_id,
        account_name=account_name,
        merchant=pending.merchant,
        note=pending.note,
        source=pending.source,
        confidence=pending.confidence,
        raw_input=pending.raw_input,
        target_transaction_id=pending.target_transaction_id,
        created_at=pending.created_at,
        expires_at=pending.expires_at,
        transaction_date=pending.transaction_date,
        timezone=pending.timezone,
    )


def _account_name_map(db: Session, pendings: list[PendingTransaction]) -> dict[uuid.UUID, str]:
    """Satu query untuk semua nama akun — menghindari N+1 saat list."""
    ids = {p.account_id for p in pendings if p.account_id is not None}
    if not ids:
        return {}
    rows = db.execute(select(Account.id, Account.account_name).where(Account.id.in_(ids))).all()
    return {row[0]: row[1] for row in rows}


def _pending_http_error(exc: ValueError) -> HTTPException:
    """Terjemahkan alasan dari pending_service menjadi status + pesan ramah."""
    reason = str(exc)
    if reason == "pending transaction expired":
        return HTTPException(
            status_code=status.HTTP_410_GONE,
            detail="Transaksi pending sudah kedaluwarsa — unggah ulang mutasi untuk memprosesnya.",
        )
    if reason == "target transaction no longer exists":
        return HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Transaksi tujuan pending ini sudah tidak ada.",
        )
    return HTTPException(
        status_code=status.HTTP_404_NOT_FOUND,
        detail="Transaksi pending tidak ditemukan.",
    )


@router.get("", response_model=PendingListResponse)
def list_pending(
    limit: int = Query(default=MAX_LIST_ITEMS, ge=1, le=MAX_LIST_ITEMS),
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> PendingListResponse:
    """
    Daftar pending aktif milik user, terbaru lebih dulu.

    Baris kedaluwarsa dibersihkan lebih dulu (tidak bisa dikonfirmasi lagi),
    sehingga tabel `pending_transactions` tidak menumpuk baris mati.
    """
    purge_expired_pendings(db, current_user.id)
    rows = list(
        db.scalars(
            select(PendingTransaction)
            .where(*_active_pending_filter(current_user.id))
            .options(selectinload(PendingTransaction.category))
            .order_by(PendingTransaction.created_at.desc())
            .limit(limit)
        )
    )
    account_names = _account_name_map(db, rows)
    return PendingListResponse(
        items=[_to_response(p, account_names) for p in rows],
        total=len(rows),
    )


@router.get("/count", response_model=PendingCountResponse)
def count_pending(
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> PendingCountResponse:
    """Jumlah pending aktif — untuk badge tombol "Matching"."""
    purge_expired_pendings(db, current_user.id)
    total = db.scalar(
        select(func.count())
        .select_from(PendingTransaction)
        .where(*_active_pending_filter(current_user.id))
    )
    return PendingCountResponse(count=int(total or 0))


@router.post("/{pending_id}/confirm", response_model=PendingConfirmResponse)
@limiter.limit("30/minute")
def confirm_pending(
    request: Request,
    pending_id: uuid.UUID,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> PendingConfirmResponse:
    """
    Konfirmasi satu pending → transaksi nyata dibuat/diubah dalam satu commit
    (pending dihapus bersamaan, jadi tidak ada jendela data ganda).
    """
    # Ambil action lebih dulu: service menghapus baris pending saat konfirmasi.
    pending_action = (
        db.scalar(
            select(PendingTransaction.action).where(
                PendingTransaction.id == pending_id,
                PendingTransaction.user_id == current_user.id,
            )
        )
        or "create"
    )
    try:
        transaction = confirm_pending_transaction(
            db,
            current_user.id,
            pending_id=pending_id,
            audit_ip_address=request.client.host if request.client else None,
        )
    except ValueError as exc:
        log.warning(
            "pending_confirm_rejected",
            user_id=str(current_user.id),
            pending_id=str(pending_id),
            reason=str(exc),
        )
        raise _pending_http_error(exc) from None

    log.info(
        "pending_confirmed_api",
        user_id=str(current_user.id),
        pending_id=str(pending_id),
        transaction_id=str(transaction.id),
    )
    return PendingConfirmResponse(
        pending_id=pending_id,
        transaction_id=transaction.id,
        action=pending_action,
        type=transaction.type,
        total_amount=transaction.total_amount,
    )


@router.post("/{pending_id}/cancel", response_model=PendingCancelResponse)
@limiter.limit("30/minute")
def cancel_pending(
    request: Request,
    pending_id: uuid.UUID,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> PendingCancelResponse:
    """Batalkan satu pending — tidak ada transaksi & tidak ada baris audit."""
    try:
        cancel_pending_transaction(db, current_user.id, pending_id=pending_id)
    except ValueError as exc:
        log.warning(
            "pending_cancel_rejected",
            user_id=str(current_user.id),
            pending_id=str(pending_id),
            reason=str(exc),
        )
        raise _pending_http_error(exc) from None

    log.info(
        "pending_cancelled_api",
        user_id=str(current_user.id),
        pending_id=str(pending_id),
    )
    return PendingCancelResponse(pending_id=pending_id)
