"""
auth_service.py — registration, login, JWT token management.

Security:
- Passwords hashed with argon2 (not bcrypt, per REQUIREMENTS.md §5 preference for argon2).
- JWT: short-lived access token (30m) + long-lived refresh token (30d).
- API keys never hardcoded — read from settings.
"""
import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.models import User
from app.schemas.schemas import UserRegisterRequest, TokenResponse

logger = structlog.get_logger(__name__)
ph = PasswordHasher()


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------
def _hash_password(password: str) -> str:
    return ph.hash(password)


def _verify_password(plain: str, hashed: str) -> bool:
    try:
        ph.verify(hashed, plain)
        return True
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def _create_token(data: dict[str, Any], expires_delta: timedelta) -> str:
    payload = data.copy()
    payload["exp"] = datetime.now(timezone.utc) + expires_delta
    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_access_token(user_id: uuid.UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "access"},
        timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(user_id: uuid.UUID) -> str:
    return _create_token(
        {"sub": str(user_id), "type": "refresh"},
        timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """Raises JWTError if invalid or expired."""
    return jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])


# ---------------------------------------------------------------------------
# Service functions — called from API layer only
# ---------------------------------------------------------------------------
async def register_user(db: AsyncSession, payload: UserRegisterRequest) -> User:
    """
    Create a new user account.
    Raises ValueError if email already exists.
    """
    result = await db.execute(select(User).where(User.email == payload.email))
    existing = result.scalar_one_or_none()
    if existing:
        raise ValueError("Email sudah terdaftar.")

    user = User(
        email=payload.email,
        password_hash=_hash_password(payload.password),
        display_name=payload.display_name,
    )
    db.add(user)
    await db.flush()  # get id before commit

    logger.info("user_registered", user_id=str(user.id), email=user.email)
    return user


async def login_user(db: AsyncSession, email: str, password: str) -> tuple[User, TokenResponse]:
    """
    Authenticate user and return token pair.
    Raises ValueError on bad credentials.
    Logs both success and failure per CODING_RULES.md §2.7 audit requirements.
    """
    result = await db.execute(select(User).where(User.email == email))
    user = result.scalar_one_or_none()

    if not user or not _verify_password(password, user.password_hash):
        logger.warning("login_failed", email=email)
        raise ValueError("Email atau password salah.")

    if not user.is_active:
        raise ValueError("Akun tidak aktif.")

    tokens = TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )

    logger.info("login_success", user_id=str(user.id))
    return user, tokens


async def refresh_tokens(db: AsyncSession, refresh_token: str) -> TokenResponse:
    """
    Validate refresh token and return a new access+refresh token pair.
    Raises ValueError if token is invalid/expired.
    """
    try:
        payload = decode_token(refresh_token)
    except JWTError:
        raise ValueError("Refresh token tidak valid atau sudah kadaluarsa.")

    if payload.get("type") != "refresh":
        raise ValueError("Token bukan refresh token.")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User tidak ditemukan.")

    return TokenResponse(
        access_token=create_access_token(user.id),
        refresh_token=create_refresh_token(user.id),
    )


async def get_current_user(db: AsyncSession, token: str) -> User:
    """
    Validate access token and return the User.
    Raises ValueError if invalid.
    """
    try:
        payload = decode_token(token)
    except JWTError:
        raise ValueError("Token tidak valid atau sudah kadaluarsa.")

    if payload.get("type") != "access":
        raise ValueError("Token bukan access token.")

    user_id = uuid.UUID(payload["sub"])
    result = await db.execute(select(User).where(User.id == user_id, User.is_active == True))
    user = result.scalar_one_or_none()
    if not user:
        raise ValueError("User tidak ditemukan.")

    return user
