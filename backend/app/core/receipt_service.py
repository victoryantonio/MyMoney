"""
receipt_service.py — parse receipt photo via Gemini 3.5 Flash-Lite (vision).

Rules per CODING_RULES.md §2.4:
- Structured output (JSON schema) via Gemini API.
- Output validated with Pydantic before entering service layer.
- confidence field returned for every parse.
- All exceptions handled explicitly — never let raw LLM error reach user.
"""
from __future__ import annotations

import base64
import json
from decimal import Decimal
from typing import Literal

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = structlog.get_logger(__name__)

_GEMINI_API_URL = (
    "https://generativelanguage.googleapis.com/v1beta/models/"
    "gemini-2.0-flash-lite:generateContent"
)

_SYSTEM_PROMPT = """
Kamu adalah parser nota belanja. Dari gambar nota yang diberikan, ekstrak informasi berikut:
- merchant: nama toko
- date: tanggal transaksi dalam format ISO 8601 (YYYY-MM-DD), atau null jika tidak ada
- total: total belanja dalam IDR (angka, bukan string)
- items: array item belanja, masing-masing dengan nama, qty, dan price
- confidence: "high" jika nota jelas dan kamu yakin, "medium" jika ada beberapa field yang diperkirakan, "low" jika nota buram/tidak lengkap/sulit dibaca

Kembalikan JSON saja, tidak ada teks lain.
""".strip()

_RESPONSE_SCHEMA = {
    "type": "object",
    "properties": {
        "merchant": {"type": ["string", "null"]},
        "date": {"type": ["string", "null"]},
        "total": {"type": "number"},
        "items": {
            "type": "array",
            "items": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "qty": {"type": "number"},
                    "price": {"type": "number"},
                },
                "required": ["name", "qty", "price"],
            },
        },
        "confidence": {"type": "string", "enum": ["high", "medium", "low"]},
    },
    "required": ["merchant", "date", "total", "items", "confidence"],
}


class ReceiptItem(BaseModel):
    name: str
    qty: Decimal = Field(gt=0)
    price: Decimal = Field(ge=0)


class ParsedReceipt(BaseModel):
    merchant: str | None
    date: str | None  # ISO date string or None
    total: Decimal = Field(gt=0)
    items: list[ReceiptItem]
    confidence: Literal["high", "medium", "low"]


class ReceiptParseError(Exception):
    """Raised when Gemini fails to return a usable structured result."""


async def parse_receipt_image(image_bytes: bytes, mime_type: str = "image/jpeg") -> ParsedReceipt:
    """
    Send receipt image to Gemini 3.5 Flash-Lite, return structured ParsedReceipt.
    Raises ReceiptParseError on any failure.
    """
    b64_image = base64.standard_b64encode(image_bytes).decode()

    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _SYSTEM_PROMPT},
                    {"inline_data": {"mime_type": mime_type, "data": b64_image}},
                ]
            }
        ],
        "generationConfig": {
            "responseMimeType": "application/json",
            "responseSchema": _RESPONSE_SCHEMA,
            "temperature": 0,
            "maxOutputTokens": 1024,
        },
    }

    try:
        async with httpx.AsyncClient(timeout=15.0) as client:
            resp = await client.post(
                _GEMINI_API_URL,
                params={"key": settings.GEMINI_API_KEY},
                json=payload,
                headers={"Content-Type": "application/json"},
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("receipt_parser_timeout")
        raise ReceiptParseError("Tidak bisa baca nota ini: timeout. Coba foto ulang atau input manual.")
    except httpx.HTTPStatusError as exc:
        logger.error("receipt_parser_http_error", status=exc.response.status_code)
        raise ReceiptParseError(f"Tidak bisa baca nota ini: error LLM ({exc.response.status_code}). Coba input manual.")

    try:
        content = resp.json()["candidates"][0]["content"]["parts"][0]["text"]
        data = json.loads(content)
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("receipt_parser_bad_response", error=str(exc))
        raise ReceiptParseError("Tidak bisa baca nota ini. Coba foto ulang dengan pencahayaan lebih baik.")

    try:
        parsed = ParsedReceipt(**data)
    except ValidationError as exc:
        logger.error("receipt_parser_validation_fail", errors=exc.errors(), raw=data)
        raise ReceiptParseError("Tidak bisa baca nota ini: data tidak valid. Coba input manual.")

    if parsed.confidence == "low":
        logger.warning("receipt_parser_low_confidence", merchant=parsed.merchant, total=str(parsed.total))

    return parsed
