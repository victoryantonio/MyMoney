"""
Security utilities: password hashing (Argon2) and JWT management.

All token creation/verification passes through this module.
Never import jwt or argon2 directly elsewhere.
"""

from datetime import UTC, datetime, timedelta
from typing import Literal

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError, VerifyMismatchError
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
TokenType = Literal["access", "refresh", "telegram_link", "password_reset"]


def _create_token(subject: str, token_type: TokenType, expires_delta: timedelta) -> str:
    """
    Internal: build and sign a JWT.

    Payload fields:
      sub  — the user's UUID as string (or telegram_id for telegram_link tokens)
      type — one of 'access' | 'refresh' | 'telegram_link' | 'password_reset'
      exp  — UTC expiry timestamp
      iat  — UTC issued-at timestamp
    """
    now = datetime.now(UTC)
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


def create_password_reset_token(user_id: str) -> str:
    """
    Create a short-lived (30-minute) password-reset token for the given user
    (UUID string). The token is emailed to the user as part of a reset link;
    no OTP is stored in the DB — verification is JWT signature + expiry.
    """
    return _create_token(
        subject=user_id,
        token_type="password_reset",
        expires_delta=timedelta(minutes=30),
    )


def decode_token(token: str, expected_type: TokenType) -> str:
    """
    Decode and validate a JWT. Returns the 'sub' claim on success.

    Raises:
        JWTError — if the token is invalid, expired, or the type doesn't match.
    """
    try:
        payload = jwt.decode(token, settings.jwt_secret_key, algorithms=[settings.jwt_algorithm])
    except JWTError:
        raise

    token_type = payload.get("type")
    if token_type != expected_type:
        raise JWTError(f"Expected token type '{expected_type}', got '{token_type}'")

    sub: str | None = payload.get("sub")
    if sub is None:
        raise JWTError("Token missing 'sub' claim")

    return sub


# ── Supabase Auth JWT verification (v2) ──────────────────────────────────────
#
# v2 auth is fully delegated to Supabase Auth. Every protected endpoint must
# verify the Bearer JWT signed by Supabase (RS256 via its JWKS endpoint) and
# then map the `sub` (auth.users UUID) to a row in `profiles`.
# No local password hashing / token issuing happens anymore.
#
# Fallback: projects that set SUPABASE_JWT_SECRET (legacy HS256 setup) can be
# verified with that shared secret instead of the JWKS endpoint.


class SupabaseJWTError(Exception):
    """Raised when a Supabase-issued JWT cannot be verified."""


_JWKS_URL_PATH = "/auth/v1/.well-known/jwks.json"
_JWKS_CACHE_TTL_SECONDS = 300  # 5 minutes; keys rotate rarely

_jwks_cache: dict | None = None
_jwks_fetched_at: float = 0.0


def _get_jwks() -> dict:
    """Fetch (and cache) the Supabase project's JWKS document."""
    global _jwks_cache, _jwks_fetched_at

    import time

    import httpx

    now = time.monotonic()
    if _jwks_cache is not None and now - _jwks_fetched_at < _JWKS_CACHE_TTL_SECONDS:
        return _jwks_cache

    url = settings.supabase_url.rstrip("/") + _JWKS_URL_PATH
    try:
        response = httpx.get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except (httpx.HTTPError, ValueError) as exc:  # network error or non-JSON body
        raise SupabaseJWTError(f"could not fetch Supabase JWKS: {exc}") from exc

    if not data.get("keys"):
        raise SupabaseJWTError("Supabase JWKS contains no keys")

    _jwks_cache = data
    _jwks_fetched_at = now
    return data


def _extract_sub(payload: dict) -> str:
    sub = payload.get("sub")
    if not sub:
        raise SupabaseJWTError("token missing 'sub' claim")
    return str(sub)


def verify_supabase_jwt(token: str) -> str:
    """
    Verify a Supabase-issued JWT via the project's JWKS endpoint (ES256 on
    current Supabase, RS256 on legacy setups) and return the `sub` claim
    (the auth.users UUID string).

    Raises:
        SupabaseJWTError — on any verification failure (bad signature, expired,
                           wrong algorithm, missing kid, etc.)
    """
    from jose import jwk as jose_jwk

    try:
        header = jwt.get_unverified_header(token)
    except JWTError as exc:
        raise SupabaseJWTError(f"malformed token: {exc}") from exc

    algorithm = header.get("alg")
    kid = header.get("kid")

    # Legacy HS256 projects verify with SUPABASE_JWT_SECRET directly.
    if algorithm == "HS256" and settings.supabase_jwt_secret:
        try:
            payload = jwt.decode(
                token,
                settings.supabase_jwt_secret,
                algorithms=["HS256"],
                options={"verify_aud": False},
            )
        except JWTError as exc:
            raise SupabaseJWTError(f"HS256 verification failed: {exc}") from exc
        return _extract_sub(payload)

    if algorithm != "RS256" and algorithm != "ES256":
        raise SupabaseJWTError(f"unsupported token algorithm '{algorithm}'")

    jwks = _get_jwks()
    key_data = next((k for k in jwks.get("keys", []) if k.get("kid") == kid), None)
    if key_data is None:
        raise SupabaseJWTError(f"no JWKS key with kid '{kid}'")

    try:
        key = jose_jwk.construct(key_data, algorithm=algorithm)
        payload = jwt.decode(
            token,
            key,
            algorithms=[algorithm],
            options={"verify_aud": False},
        )
    except (JWTError, ValueError) as exc:
        raise SupabaseJWTError(f"{algorithm} verification failed: {exc}") from exc

    return _extract_sub(payload)
