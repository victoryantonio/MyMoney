"""
Security utilities: password hashing (Argon2) and JWT management.

All token creation/verification passes through this module.
Never import jwt or argon2 directly elsewhere.
"""

from datetime import datetime, timedelta, timezone
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import VerifyMismatchError, VerificationError, InvalidHashError
from jose import JWTError, jwt

from app.core.config import settings

# ── Argon2 password hashing ────────────────────────────────────────────────
# time_cost=2, memory_cost=65536 (64 MB), parallelism=2 — OWASP recommended defaults
_ph = PasswordHasher(time_cost=2, memory_cost=65536, parallelism=2)


def hash_password(plain: str) -> str:
    """Hash a plaintext password using Argon2id. Returns the encoded hash string."""
    return _ph.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """
    Verify a plaintext password against an Argon2 hash.
    Returns False instead of raising on mismatch — never leak exception details to callers.
    """
    try:
        return _ph.verify(hashed, plain)
    except (VerifyMismatchError, VerificationError, InvalidHashError):
        return False


def needs_rehash(hashed: str) -> bool:
    """Return True if the stored hash uses outdated parameters and should be upgraded."""
    return _ph.check_needs_rehash(hashed)


# ── JWT token creation ─────────────────────────────────────────────────────
TokenType = Literal["access", "refresh", "telegram_link"]


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    """
    Internal: build and sign a JWT.

    Payload fields:
      sub  — the user's UUID as string (or telegram_id for telegram_link tokens)
      type — one of 'access' | 'refresh' | 'telegram_link'
      exp  — UTC expiry timestamp
      iat  — UTC issued-at timestamp
    """
    now = datetime.now(timezone.utc)
    payload = {
        "sub": subject,
        "type": token_type,
        "iat": now,
        "exp": now + expires_delta,
    }
    return jwt.encode(payload, settings.jwt_secret_key, algorithm=settings.jwt_algorithm)


def create_access_token(user_id: str) -> str:
    """Create a short-lived JWT access token for the given user_id (UUID string)."""
    return _create_token(
        subject=user_id,
        token_type="access",
        expires_delta=timedelta(minutes=settings.jwt_access_token_expire_minutes),
    )


def create_refresh_token(user_id: str) -> str:
    """Create a long-lived JWT refresh token for the given user_id (UUID string)."""
    return _create_token(
        subject=user_id,
        token_type="refresh",
        expires_delta=timedelta(days=settings.jwt_refresh_token_expire_days),
    )


def create_telegram_link_token(telegram_id: int) -> str:
    """
    Create a short-lived (10-minute) linking token that encodes a Telegram user ID.
    Used in the SSO linking flow: bot → generates token → user clicks link → backend validates.
    """
    return _create_token(
        subject=str(telegram_id),
        token_type="telegram_link",
        expires_delta=timedelta(minutes=10),
    )


def decode_token(token: str, expected_type: TokenType) -> str:
    """
    Decode and validate a JWT. Returns the 'sub' claim on success.

    Raises:
        JWTError — if the token is invalid, expired, or the type doesn't match.
    """
    try:
        payload = jwt.decode(
            token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm]
        )
    except JWTError:
        raise

    token_type = payload.get("type")
    if token_type != expected_type:
        raise JWTError(f"Expected token type '{expected_type}', got '{token_type}'")

    sub: str | None = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing 'sub' claim")

    return sub
