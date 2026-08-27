"""
API tests for receipt OCR (POST /api/receipts/ocr) — dipakai fitur "Scan Nota"
app Flutter (REQUIREMENTS US-07..US-10).

Vision LLM di-mock (parse_receipt_image); logika parsing & validasi asli
sudah diuji unit di test_receipt_ocr.py. Butuh Postgres + Supabase creds
(sama seperti test API lain).
"""

from unittest.mock import AsyncMock, patch

import pytest
from fastapi.testclient import TestClient

from app.core.receipt_ocr import ParsedReceipt, ReceiptItem
from app.main import app

client = TestClient(app)


@pytest.fixture
def auth(supabase_factory):
    """Fresh Supabase user per test → Bearer headers (skip di CI tanpa creds)."""
    return supabase_factory


def _upload(headers: dict[str, str] | None = None, content: bytes = b"fake-jpeg"):
    return client.post(
        "/api/receipts/ocr",
        files={"file": ("nota.jpg", content, "image/jpeg")},
        headers=headers,
    )


def _upload(headers: dict[str, str] | None = None, content: bytes = b"fake-jpeg"):
    return client.post(
        "/api/receipts/ocr",
        files={"file": ("nota.jpg", content, "image/jpeg")},
        headers=headers,
    )


def test_ocr_requires_auth():
    """Tanpa JWT → 401, LLM tidak boleh dipanggil."""
    with patch("app.api.receipts.parse_receipt_image", new_callable=AsyncMock) as mock_parse:
        resp = _upload()
        assert resp.status_code == 401
        mock_parse.assert_not_awaited()


def test_ocr_empty_file_rejected(auth):
    """File kosong → 422 sebelum LLM dipanggil."""
    with patch("app.api.receipts.parse_receipt_image", new_callable=AsyncMock) as mock_parse:
        headers = auth("ocr_empty")
        resp = _upload(headers, content=b"")
        assert resp.status_code == 422
        mock_parse.assert_not_awaited()


def test_ocr_unrecognized_returns_422(auth):
    """Foto tidak terbaca → 422 dengan pesan jelas (client minta foto ulang)."""
    with patch("app.api.receipts.parse_receipt_image", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = None
        headers = auth("ocr_unrec")
        resp = _upload(headers)
        assert resp.status_code == 422
        assert "not recognized" in resp.json()["detail"]


def test_ocr_success_returns_parsed_receipt(auth):
    """Foto terbaca → ParsedReceipt lengkap (merchant, type, items)."""
    parsed = ParsedReceipt(
        type="expense",
        merchant="Mixue",
        category="Food",
        items=[
            ReceiptItem(name="Ice Cream Tofee (M)", qty=2, price=21000),
            ReceiptItem(name="Teh Botol", qty=1, price=5000),
        ],
    )
    with patch("app.api.receipts.parse_receipt_image", new_callable=AsyncMock) as mock_parse:
        mock_parse.return_value = parsed

        headers = auth("ocr_ok")
        resp = _upload(headers)
        assert resp.status_code == 200

        data = resp.json()
        assert data["type"] == "expense"
        assert data["merchant"] == "Mixue"
        assert data["category"] == "Food"
        assert len(data["items"]) == 2
        assert data["items"][0]["name"] == "Ice Cream Tofee (M)"
        # Decimal qty/price dikirim sebagai angka (jsonable_encoder).
        assert float(data["items"][0]["price"]) == 21000.0
