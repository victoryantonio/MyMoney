"""
Authentication API routes.

POST /api/auth/register  — create a new user account
POST /api/auth/login     — authenticate and receive JWT tokens
POST /api/auth/refresh   — exchange a refresh token for a new access token
GET  /api/auth/me        — return the current user's profile
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user, require_active_user
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    hash_password,
    needs_rehash,
    verify_password,
)
from app.db.session import get_db
from app.models.user import User
from app.schemas.auth import (
    AccessTokenResponse,
    RefreshTokenRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserResponse,
)

log = structlog.get_logger()
router = APIRouter(prefix="/api/auth", tags=["Auth"])


@router.post("/register", response_model=UserResponse, status_code=status.HTTP_201_CREATED)
def register(body: UserRegisterRequest, db: Session = Depends(get_db)) -> User:
    """
    Register a new user account.

    Returns HTTP 409 if the email is already taken.
    Passwords are hashed with Argon2id before storage — the plaintext is never persisted.
    """
    # Check for duplicate email (case-insensitive via DB unique index on lowercased value)
    existing = db.scalar(select(User).where(User.email == body.email.lower()))
    if existing is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="An account with this email already exists",
        )

    user = User(
        id=uuid.uuid4(),
        email=body.email.lower(),
        password_hash=hash_password(body.password),
        display_name=body.display_name.strip(),
        timezone=body.timezone,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    log.info("user_registered", user_id=str(user.id), email=user.email)
    return user


@router.post("/login", response_model=TokenResponse)
def login(body: UserLoginRequest, db: Session = Depends(get_db)) -> dict:
    """
    Authenticate with email + password.

    Deliberately uses the same error message for wrong email OR wrong password
    to avoid user enumeration attacks.
    """
    _auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise _auth_error

    if not verify_password(body.password, user.password_hash):
        log.warning("login_failed", email=body.email)
        raise _auth_error

    if not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Account is deactivated",
        )

    # Opportunistically rehash if Argon2 parameters have been updated
    if needs_rehash(user.password_hash):
        user.password_hash = hash_password(body.password)
        db.commit()

    log.info("login_success", user_id=str(user.id))
    return {
        "access_token": create_access_token(str(user.id)),
        "refresh_token": create_refresh_token(str(user.id)),
        "token_type": "bearer",
    }


@router.post("/refresh", response_model=AccessTokenResponse)
def refresh_access_token(body: RefreshTokenRequest, db: Session = Depends(get_db)) -> dict:
    """
    Exchange a valid refresh token for a new access token.
    The refresh token itself is NOT rotated here (stateless approach for Phase 1).
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid or expired refresh token",
    )
    try:
        from jose import JWTError
        user_id_str = decode_token(body.refresh_token, expected_type="refresh")
    except Exception:
        raise credentials_exception

    try:
        user_id = uuid.UUID(user_id_str)
    except ValueError:
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    return {
        "access_token": create_access_token(str(user.id)),
        "token_type": "bearer",
    }


@router.get("/me", response_model=UserResponse)
def get_me(current_user: User = Depends(require_active_user)) -> User:
    """Return the currently authenticated user's profile."""
    return current_user
