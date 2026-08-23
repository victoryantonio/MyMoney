"""
FastAPI dependencies — injected into route handlers via Depends().

Key dependencies:
  - get_db      : yields a SQLAlchemy session per request (from session.py)
  - get_current_user  : validates JWT Bearer token, returns the authenticated User ORM object
  - require_active_user: same but also checks is_active=True
"""

import uuid

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jose import JWTError
from sqlalchemy.orm import Session

from app.core.security import decode_token
from app.db.session import get_db
from app.models.user import User

# HTTPBearer auto-reads the Authorization: Bearer <token> header
_bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """
    Validate the JWT access token and return the corresponding User.

    Raises HTTP 401 if:
      - No Authorization header is present
      - The token is invalid or expired
      - The token type is not 'access'
      - The user_id in the token doesn't exist in the database
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise credentials_exception

    try:
        user_id_str = decode_token(credentials.credentials, expected_type="access")
        user_id = uuid.UUID(user_id_str)
    except (JWTError, ValueError):
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None:
        raise credentials_exception

    return user


def require_active_user(current_user: User = Depends(get_current_user)) -> User:
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
