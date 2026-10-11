"""
Profile API routes — setelan user (timezone, nama tampilan).

Endpoint:
  GET   /api/profile   → timezone, timezone_confirmed, display_name
  PATCH /api/profile   → ubah timezone dan/atau display_name

Timezone di-*snapshot* ke `transactions.timezone` saat transaksi dibuat, jadi
mengubah setelan di sini TIDAK menggeser interpretasi transaksi lama — hanya
memengaruhi transaksi baru, tampilan "sekarang" (periode laporan), dan jam
transaksi baru.

`timezone_confirmed` = false berarti user belum pernah memilih timezone secara
eksplisit → aplikasi menampilkan form timezone (default timezone HP) saat
pertama login. PATCH dengan `timezone` otomatis menandainya true.
"""

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.deps import require_active_user
from app.core.audit_service import record_audit
from app.core.rate_limit import limiter
from app.db.session import get_db
from app.models.profile import Profile
from app.schemas.profile import ProfileResponse, ProfileUpdateRequest

router = APIRouter(prefix="/api/profile", tags=["Profile"])


@router.get("", response_model=ProfileResponse)
def get_profile(current_user: Profile = Depends(require_active_user)) -> Profile:
    """Setelan profil user yang sedang login (dibuat otomatis oleh trigger signup)."""
    return current_user


@router.patch("", response_model=ProfileResponse)
@limiter.limit("30/minute")
def update_profile(
    request: Request,
    body: ProfileUpdateRequest,
    current_user: Profile = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> Profile:
    """Update parsial profil. Timezone divalidasi terhadap database IANA."""
    changed: dict[str, str] = {}

    if body.display_name is not None:
        current_user.display_name = body.display_name
        changed["display_name"] = body.display_name

    if body.timezone is not None:
        current_user.timezone = body.timezone
        # User memilih eksplisit → onboarding tidak perlu muncul lagi.
        current_user.timezone_confirmed = True
        changed["timezone"] = body.timezone

    if changed:
        record_audit(
            db,
            user_id=current_user.id,
            action="update",
            entity_type="profile",
            entity_id=current_user.id,
            new_value=changed,
            source="app",
        )

    db.commit()
    db.refresh(current_user)
    return current_user
