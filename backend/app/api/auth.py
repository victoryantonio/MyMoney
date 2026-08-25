"""
Authentication API routes.

POST /api/auth/register        — create a new user account
POST /api/auth/login           — authenticate and receive JWT tokens
POST /api/auth/refresh         — exchange a refresh token for a new access token
GET  /api/auth/me              — return the current user's profile
POST /api/auth/forgot-password — request a password reset link (anti-enumeration)
POST /api/auth/reset-password  — exchange a reset token for a new password
"""

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import require_active_user
from app.core.audit_service import record_audit
from app.core.config import settings
from app.core.rate_limit import limiter
from app.core.security import (
    create_access_token,
    create_password_reset_token,
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
    ForgotPasswordRequest,
    RefreshTokenRequest,
    ResetPasswordRequest,
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
@limiter.limit("10/minute")
def login(body: UserLoginRequest, request: Request, db: Session = Depends(get_db)) -> dict:
    """
    Authenticate with email + password.

    Deliberately uses the same error message for wrong email OR wrong password
    to avoid user enumeration attacks. Success/failure is audited (CODING_RULES
    §2.6); failed logins for unknown emails cannot be audited because the
    audit_logs.user_id column is NOT NULL.
    """
    _auth_error = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid email or password",
    )
    client_ip = request.client.host if request.client else None

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None:
        raise _auth_error

    if not verify_password(body.password, user.password_hash):
        log.warning("login_failed", email=body.email)
        record_audit(
            db,
            user_id=user.id,
            action="login_failed",
            entity_type="auth",
            source="app",
            ip_address=client_ip,
        )
        db.commit()
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
    record_audit(
        db,
        user_id=user.id,
        action="login",
        entity_type="auth",
        source="app",
        ip_address=client_ip,
    )
    db.commit()
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


@router.post("/forgot-password", status_code=status.HTTP_200_OK)
def forgot_password(body: ForgotPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """
    Step 1 of password reset — ALWAYS returns the same generic message,
    regardless of whether the email exists (anti user-enumeration, §10 security).

    If the email IS registered: generate a short-lived signed reset token
    (30 min, type=password_reset) and deliver a reset link.

    Delivery: no SMTP is configured in this deployment yet, so the reset link
    is logged to the server log (structlog). Wire this to a real email provider
    by adding SMTP settings to config and swapping the log call for a send.
    """
    generic_message = {
        "message": "If that email is registered, we've sent a password reset link to it.",
    }

    user = db.scalar(select(User).where(User.email == body.email.lower()))
    if user is None or not user.is_active:
        # Burn identical work regardless of existence (timing-side hygiene).
        return generic_message

    token = create_password_reset_token(str(user.id))
    reset_url = f"{settings.app_base_url}/reset-password?token={token}"
    log.info(
        "password_reset_link_generated",
        user_id=str(user.id),
        email=user.email,
        reset_url=reset_url,
        expires_in_minutes=30,
    )
    # TODO(phase-2): send `reset_url` via email (SMTP) instead of logging it.
    return generic_message


@router.post("/reset-password", status_code=status.HTTP_200_OK)
def reset_password(body: ResetPasswordRequest, db: Session = Depends(get_db)) -> dict:
    """
    Step 2 of password reset — verify the signed token and set a new password.

    The token is a JWT (type=password_reset, 30 min expiry). A single-use
    guarantee is out of scope for Phase 1 (stateless tokens); the short expiry
    bounds the window.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_400_BAD_REQUEST,
        detail="Invalid or expired reset token",
    )
    try:
        user_id_str = decode_token(body.token, expected_type="password_reset")
        user_id = uuid.UUID(user_id_str)
    except Exception:
        raise credentials_exception

    user = db.get(User, user_id)
    if user is None or not user.is_active:
        raise credentials_exception

    user.hashed_password = hash_password(body.new_password)
    record_audit(
        db,
        user_id=user.id,
        action="update",
        entity_type="user",
        entity_id=user.id,
        new_value={"password_reset": True},
        source="app",
    )
    db.commit()
    log.info("password_reset_completed", user_id=str(user.id))
    return {"message": "Password has been reset. You can now log in."}
