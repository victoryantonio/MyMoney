"""
Tests for auth_service — password hashing and token creation/validation.
These are pure unit tests: no DB access, no LLM calls.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt

from app.core.auth_service import (
    _hash_password,
    _verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
)
from app.core.config import settings
import uuid


def test_password_hash_and_verify():
    password = "SuperSecret123!"
    hashed = _hash_password(password)
    assert hashed != password
    assert _verify_password(password, hashed) is True
    assert _verify_password("wrongpassword", hashed) is False


def test_create_access_token():
    user_id = uuid.uuid4()
    token = create_access_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "access"


def test_create_refresh_token():
    user_id = uuid.uuid4()
    token = create_refresh_token(user_id)
    payload = decode_token(token)
    assert payload["sub"] == str(user_id)
    assert payload["type"] == "refresh"


def test_decode_invalid_token_raises():
    from jose import JWTError
    with pytest.raises(JWTError):
        decode_token("invalid.token.value")
