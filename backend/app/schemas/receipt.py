"""
Pydantic schema respons `POST /api/receipts/ocr`.

`ParsedReceipt` adalah hasil ekstraksi vision LLM apa adanya. Endpoint ini
menambahkan hasil *penilaian kualitas* dari `app/core/parse_score.py` supaya
app tahu seberapa layak hasil itu dipakai tanpa pemeriksaan tambahan.

Bands:
  high   → hasil lengkap (merchant, item, tanggal/kategori jelas); app boleh
           menampilkan form yang sudah terisi tanpa peringatan.
  medium → sebagian sinyal hilang; app menampilkan peringatan "periksa dulu".
  low    → banyak sinyal hilang; app meminta user mengisi ulang manual.

Sesuai CODING_RULES §2.4 hasil LLM tetap tidak pernah disimpan langsung, jadi
`needs_confirm` selalu `True` untuk hasil di bawah band `high`.
"""

from decimal import Decimal

from pydantic import Field

from app.core.receipt_ocr import ParsedReceipt


class ReceiptOcrResponse(ParsedReceipt):
    """`ParsedReceipt` + hasil skoring deterministik di server."""

    confidence: str = Field(
        default="low",
        description="Band hasil `score_parse`: high | medium | low",
    )
    confidence_score: Decimal = Field(
        default=Decimal("0"),
        description="Skor 0.00..1.00 hasil penilaian aturan di app/core/parse_score.py",
    )
    confidence_reasons: list[str] = Field(
        default_factory=list,
        description="Alasan yang menaikkan/menurunkan skor (untuk diagnosa & UI)",
    )
    needs_confirm: bool = Field(
        default=True,
        description="True bila band != high, artinya user wajib memeriksa sebelum simpan",
    )
