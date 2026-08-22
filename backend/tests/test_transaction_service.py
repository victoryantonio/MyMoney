"""
Tests for transaction_service cursor encoding/decoding.
No DB required — pure logic unit tests.
"""
import uuid
from datetime import datetime, timezone
from app.core.transaction_service import _encode_cursor, _decode_cursor


def test_cursor_roundtrip():
    now = datetime.now(timezone.utc)
    tx_id = uuid.uuid4()
    cursor = _encode_cursor(now, tx_id)
    decoded_date, decoded_id = _decode_cursor(cursor)
    # datetime comparison must be timezone-aware
    assert decoded_date == now
    assert decoded_id == tx_id


def test_cursor_is_url_safe_string():
    now = datetime.now(timezone.utc)
    tx_id = uuid.uuid4()
    cursor = _encode_cursor(now, tx_id)
    # Must be a plain URL-safe base64 string (no spaces, +, /)
    assert " " not in cursor
    assert "+" not in cursor
