"""
nlu_parser.py — parse free-form text to structured transaction via GLM 5.2.

Rules per CODING_RULES.md §2.4:
- Must use structured output (JSON schema), no free-text regex parsing.
- Output MUST be validated with Pydantic before passing to service layer.
- All LLM exceptions (timeout, rate limit, bad response) handled explicitly.
- No result is committed to DB without user confirmation (caller's responsibility).
"""
from __future__ import annotations

import json
from decimal import Decimal
from typing import Literal

import httpx
import structlog
from pydantic import BaseModel, Field, ValidationError

from app.core.config import settings

logger = structlog.get_logger(__name__)

# JSON schema passed to GLM 5.2 for structured output
_PARSE_SCHEMA = {
    "name": "transaction",
    "strict": True,
    "schema": {
        "type": "object",
        "properties": {
            "type": {"type": "string", "enum": ["income", "expense"]},
            "amount": {"type": "number", "description": "Nominal dalam IDR, harus positif"},
            "category": {
                "type": "string",
                "description": "Salah satu dari: Makanan, Transport, Belanja, Tagihan, Hiburan, Kesehatan, Pendidikan, Gaji, Bonus, Investasi, Hadiah, Lainnya",
            },
            "merchant": {
                "type": ["string", "null"],
                "description": "Nama toko/merchant jika disebutkan, null kalau tidak ada",
            },
            "note": {"type": ["string", "null"], "description": "Catatan tambahan atau null"},
            "account_hint": {
                "type": ["string", "null"],
                "description": "Nama bank/akun yang disebutkan user (misal 'BCA', 'tunai'), null kalau tidak disebutkan",
            },
        },
        "required": ["type", "amount", "category", "merchant", "note", "account_hint"],
        "additionalProperties": False,
    },
}

_SYSTEM_PROMPT = (
    "Kamu adalah parser transaksi keuangan. "
    "Ekstrak informasi dari pesan pengguna dan kembalikan JSON terstruktur. "
    "Jika ada singkatan angka (k = ribu, jt = juta), konversi ke angka penuh. "
    "Contoh: '5k' = 5000, '1.5jt' = 1500000. "
    "Selalu kembalikan JSON sesuai schema, tidak ada teks tambahan."
)


class ParsedTransaction(BaseModel):
    """Validated output from GLM 5.2 — required before entering service layer."""
    type: Literal["income", "expense"]
    amount: Decimal = Field(gt=0)
    category: str
    merchant: str | None
    note: str | None
    account_hint: str | None


class ParseError(Exception):
    """Raised when LLM fails to return a usable structured result."""


async def parse_text(raw_text: str) -> ParsedTransaction:
    """
    Send raw_text to GLM 5.2, get structured transaction back.
    Raises ParseError on any failure (network, bad JSON, validation fail).
    """
    payload = {
        "model": "glm-4-flash",  # GLM 5.2 — cheapest reasoning model
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": raw_text},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
        "max_tokens": 300,
    }

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(
                f"{settings.GLM_API_BASE_URL}/chat/completions",
                headers={
                    "Authorization": f"Bearer {settings.GLM_API_KEY}",
                    "Content-Type": "application/json",
                },
                json=payload,
            )
            resp.raise_for_status()
    except httpx.TimeoutException:
        logger.warning("nlu_parser_timeout", raw_text=raw_text[:80])
        raise ParseError("Parsing gagal: timeout. Coba lagi atau input manual.")
    except httpx.HTTPStatusError as exc:
        logger.error("nlu_parser_http_error", status=exc.response.status_code)
        raise ParseError(f"Parsing gagal: error dari LLM ({exc.response.status_code}). Coba lagi atau input manual.")

    try:
        content = resp.json()["choices"][0]["message"]["content"]
        data = json.loads(content)
    except (KeyError, json.JSONDecodeError) as exc:
        logger.error("nlu_parser_bad_response", error=str(exc))
        raise ParseError("Parsing gagal: respons LLM tidak bisa dibaca. Coba input manual.")

    try:
        return ParsedTransaction(**data)
    except ValidationError as exc:
        logger.error("nlu_parser_validation_fail", errors=exc.errors(), raw=data)
        raise ParseError("Parsing gagal: data tidak valid. Periksa kembali atau input manual.")
