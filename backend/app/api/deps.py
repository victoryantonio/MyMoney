"""
FastAPI dependencies — injected into route handlers via Depends().

v2 auth model:
  - All tokens are issued by Supabase Auth (RS256, verified via the project's
    JWKS endpoint). The backend never issues its own access tokens.
  - `sub` of the verified token is an auth.users UUID; it maps 1:1 to a row
    in `profiles`.

Key dependencies:
  - get_db            : yields a SQLAlchemy session per request
  - get_current_user  : verifies the Supabase Bearer JWT → Profile ORM object
  - require_active_user : same + rejects deactivated profiles (403)

Note (keputusan 2026-08-26): tidak ada role admin di sistem ini — semua user
self-register. `require_role` dihapus bersama kolom `profiles.role` (migration 0007).
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import SupabaseJWTError, verify_supabase_jwt
from app.db.session import get_db
from app.models.profile import Profile

# HTTPBearer auto-reads the Authorization: Bearer <token> header
_bearer_scheme = HTTPBearer(auto_error=False)

_credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> Profile:
    """
    Verify the Supabase JWT and return the corresponding Profile.

    Raises HTTP 401 if:
      - No Authorization header is present
      - The token signature/expiry is invalid (SupabaseJWTError)
      - The auth.users UUID in the token has no profile row
    """
    if credentials is None:
        raise _credentials_exception

    try:
        user_id_str = verify_supabase_jwt(credentials.credentials)
        user_id = uuid.UUID(user_id_str)
    except (SupabaseJWTError, ValueError):
        raise _credentials_exception

    profile = db.get(Profile, user_id)
    if profile is None:
        # Profile auto-created by the Supabase trigger on signup — missing
        # means the account predates the trigger or was deleted.
        raise _credentials_exception

    return profile


def require_active_user(current_user: Profile = Depends(get_current_user)) -> Profile:
    """
    Same as get_current_user but additionally rejects deactivated accounts.
    Use this for all data-mutating endpoints.
    """
    if not current_user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )
    return current_user
