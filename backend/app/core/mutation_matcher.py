"""
Matching Mutasi — pencocokan mutasi bank dengan transaksi tercatat.

Alur (REQUIREMENTS — fitur "Matching Mutasi", menu Dashboard → Upload):

  1. User mengunggah bukti mutasi (screenshot/foto aplikasi bank, CSV, atau PDF
     e-statement).
  2. Vision LLM mengekstrak baris-baris mutasi (tanggal, keterangan, nominal,
     arah dana debit/kredit). PDF diekstrak teksnya lebih dulu (murah & akurat);
     hanya PDF hasil scan yang di-render ke gambar lalu dibaca vision LLM
     (satu halaman per satu halaman, tanpa batas jumlah halaman).
  3. Setiap baris mutasi dicocokkan dengan transaksi di sistem:
     nominal sama (toleransi kecil) + arah dana cocok + jarak tanggal ≤ N hari
     + akun yang sama (bila user memilih akun).
  4. Baris mutasi yang TIDAK ketemu → dibuat sebagai `pending_transaction`
     (belum jadi transaksi nyata) supaya user mengonfirmasi dulu — sesuai
     CODING_RULES §2.4: "tidak ada hasil parsing LLM yang langsung commit".

Tidak ada penulisan Transaction di modul ini. Menambah transaksi tetap lewat
`POST /api/transactions` atau alur konfirmasi pending.
"""

import base64
import json
import re
import uuid
from collections.abc import Iterator
from datetime import UTC, date, datetime, timedelta
from decimal import Decimal, InvalidOperation

import structlog
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session

try:  # pragma: no cover - guard agar app tetap jalan tanpa PyMuPDF
    import fitz  # PyMuPDF

except ImportError:  # pragma: no cover
    fitz = None  # type: ignore[assignment]

from app.core.llm_client import VISION_MODELS, call_llm
from app.models.account import Account
from app.models.category import Category, category_visible_clause
from app.models.transaction import Transaction

log = structlog.get_logger()

# ── Default tuning ────────────────────────────────────────────────────────────

# Nominal dianggap "balance" bila selisihnya ≤ toleransi ini. Mutasi bank
# kadang berbeda beberapa rupiah karena pembulatan admin.
DEFAULT_AMOUNT_TOLERANCE = Decimal("1.00")
# Tanggal transaksi boleh berbeda beberapa hari dari tanggal mutasi (mutasi
# bank bisa muncul H+1..H+3 setelah transaksi terjadi).
DEFAULT_DATE_WINDOW_DAYS = 3

TEXT_MIME_PREFIXES = ("text/",)
TEXT_EXTENSIONS = (".csv", ".txt", ".tsv")

# ── PDF (e-statement bank) ────────────────────────────────────────────────────

PDF_MIME_TYPES = ("application/pdf", "application/x-pdf")
PDF_EXTENSIONS = (".pdf",)
PDF_MAGIC = b"%PDF-"
# Tidak ada batas jumlah halaman: halaman di-render & dibaca satu per satu
# (lazy) sehingga e-statement panjang tetap aman memori. Batas praktisnya
# adalah ukuran unggahan (MAX_UPLOAD_BYTES di API).
PDF_RENDER_DPI = 200
# Di bawah ini dianggap PDF tidak punya layer teks (hasil scan) → render ke gambar.
MIN_PDF_TEXT_CHARS = 40


# ── Hasil ekstraksi LLM ───────────────────────────────────────────────────────


class ParsedMutation(BaseModel):
    """Satu baris mutasi bank hasil ekstraksi LLM."""

    date: str | None = None  # ISO yyyy-mm-dd
    time: str | None = None  # HH:MM
    description: str = Field(min_length=1, max_length=200)
    amount: Decimal = Field(gt=0)
    direction: str = Field(pattern="^(debit|credit)$")  # debit = dana keluar


class MutationExtraction(BaseModel):
    account_hint: str | None = None
    mutations: list[ParsedMutation] = Field(default_factory=list)


# Hardcoded system prompt — never influenced by user input (CODING_RULES §2.9.B).
_SYSTEM_PROMPT = """You are a bank statement (mutasi rekening) reader for the
'MyMoney' app. Read the bank statement in the image and extract EVERY
transaction row into JSON.

Respond ONLY with a valid JSON object, no markdown, no backticks, no
explanations.
Schema:
{
  "account_hint": string or null  (account/card name shown on the statement,
                                   e.g. "BCA", "Mandiri", "GoPay" — null if not
                                   visible),
  "mutations": [
    {
      "date": string "yyyy-mm-dd" (null if not visible),
      "time": string "HH:MM" (null if not visible),
      "description": string  (the transaction description exactly as printed,
                              e.g. "TRANSFER KE 1234567890", "QRIS MIXUE"),
      "amount": number  (positive number, thousands separators removed:
                         "21.000" -> 21000, "1,250,000.00" -> 1250000),
      "direction": "debit" or "credit"
    }
  ]
}

Rules:
- `debit` = money LEAVING the account (pengeluaran / DB / DEBET / -).
- `credit` = money ENTERING the account (pemasukan / CR / KREDIT / +).
- Never include the running balance (saldo) as a mutation.
- Never include subtotal / total / "Saldo Awal" / "Saldo Akhir" rows.
- `amount` is always positive; the SIGN is expressed by `direction`.
- If the currency uses a decimal comma and dot thousands ("1.250.000,50"),
  interpret dot as thousands separator and comma as decimal point.
- Currency is IDR unless the statement clearly shows another currency.
- Skip rows you cannot read confidently rather than guessing a number.
"""

_RETRY_PROMPT = """The previous attempt failed. Read this bank statement image
again and reply with ONLY this JSON shape:
{"account_hint": null, "mutations": [{"date": "yyyy-mm-dd", "time": "HH:MM",
"description": "text as printed", "amount": 21000, "direction": "debit"}]}
Every row where money left the account is "debit"; money entering is "credit".
Skip running-balance rows. No prose, JSON only.
"""


def _parse_llm_json(content: str) -> MutationExtraction | None:
    """Parse LLM output → MutationExtraction; None bila tidak valid."""
    if not content:
        return None
    text = content.strip()
    fence = re.search(r"```(?:json)?\s*(.*?)```", text, re.DOTALL)
    if fence:
        text = fence.group(1).strip()
    start, end = text.find("{"), text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        return None
    try:
        raw = json.loads(text[start : end + 1])
    except json.JSONDecodeError:
        return None
    if not isinstance(raw, dict):
        return None

    mutations: list[ParsedMutation] = []
    for row in raw.get("mutations") or []:
        if not isinstance(row, dict):
            continue
        description = str(row.get("description") or "").strip()
        if not description:
            continue
        amount = _to_decimal(row.get("amount"))
        if amount is None or amount <= 0:
            continue
        direction = _normalize_direction(row.get("direction"), row.get("amount"))
        if direction is None:
            continue
        mutations.append(
            ParsedMutation(
                date=_normalize_date(row.get("date")),
                time=_normalize_time(row.get("time")),
                description=description[:200],
                amount=amount,
                direction=direction,
            )
        )

    if not mutations:
        return None
    hint = raw.get("account_hint")
    return MutationExtraction(
        account_hint=str(hint)[:100] if hint else None,
        mutations=mutations,
    )


def _to_decimal(value) -> Decimal | None:
    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, int | float | Decimal):
        return Decimal(str(value))
    # Buang simbol mata uang & spasi; dukung "1.250.000,50" dan "1,250,000.50".
    text = re.sub(r"[^\d.,-]", "", str(value).strip())
    if not text:
        return None
    try:
        return Decimal(_normalize_separators(text))
    except InvalidOperation:
        return None


def _normalize_separators(text: str) -> str:
    """Ubah pemisah ribuan/desimal gaya id-ID maupun en-US → format Decimal."""
    dots, commas = text.count("."), text.count(",")
    if dots and commas:
        # Pemisah yang muncul TERAKHIR adalah pemisah desimal.
        decimal_sep = "." if text.rfind(".") > text.rfind(",") else ","
        thousand_sep = "," if decimal_sep == "." else "."
        return text.replace(thousand_sep, "").replace(decimal_sep, ".")
    if dots:
        return _collapse_separator(text, ".")
    if commas:
        return _collapse_separator(text, ",")
    return text


def _collapse_separator(text: str, sep: str) -> str:
    """Satu jenis pemisah: ribuan bila semua grup 3 digit, selain itu desimal.

    "21.000" → 21000 (ribuan) tetapi "21.5" → 21.5 (desimal).
    """
    parts = text.split(sep)
    if len(parts) > 2:  # "1.250.000" — pasti ribuan
        return text.replace(sep, "")
    head, _, tail = text.rpartition(sep)
    head_digits = head.lstrip("-")
    if not head_digits.isdigit():
        return text.replace(sep, "")
    if len(tail) == 3 and head_digits != "0":
        return text.replace(sep, "")  # ribuan
    if len(tail) in (1, 2):
        return f"{head}.{tail}"  # desimal
    return text.replace(sep, "")


def _normalize_direction(direction, raw_amount) -> str | None:
    if isinstance(direction, str):
        norm = direction.strip().lower()
        if norm in ("debit", "db", "debet", "out", "keluar", "expense", "-"):
            return "debit"
        if norm in ("credit", "cr", "kredit", "in", "masuk", "income", "+"):
            return "credit"
    # Fallback: tanda pada nilai mentah.
    if isinstance(raw_amount, int | float) and raw_amount < 0:
        return "debit"
    if isinstance(raw_amount, str) and raw_amount.strip().startswith("-"):
        return "debit"
    return None


def _normalize_date(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # dd-mm-yyyy / dd/mm/yyyy
    match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", text)
    if match:
        day, month, year = match.groups()
        year = year if len(year) == 4 else f"20{year}"
        text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    try:
        return date.fromisoformat(text[:10]).isoformat()
    except ValueError:
        return None


def _normalize_time(value) -> str | None:
    if value is None:
        return None
    text = str(value).strip()
    match = re.match(r"^(\d{1,2})[:.](\d{2})", text)
    if not match:
        return None
    hour, minute = int(match.group(1)), int(match.group(2))
    if hour > 23 or minute > 59:
        return None
    return f"{hour:02d}:{minute:02d}"


async def parse_mutation_image(image_bytes: bytes, mime_type: str) -> MutationExtraction | None:
    """Kirim gambar mutasi ke vision LLM; kembali MutationExtraction atau None."""
    if not image_bytes:
        return None

    data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode()}"
    user_content = [
        {"type": "text", "text": "Extract every mutation row from this bank statement."},
        {"type": "image_url", "image_url": {"url": data_url}},
    ]
    result = await call_llm(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": user_content},
        ],
        models=VISION_MODELS,
        temperature=0.0,
        parser=_parse_llm_json,
    )
    if result is None:
        # Percobaan kedua dengan prompt lebih longgar (kualitas screenshot
        # bank beragam: watermark, kontras rendah, hasil screenshot panjang).
        result = await call_llm(
            [
                {"role": "system", "content": _RETRY_PROMPT},
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "Best-effort: extract the mutation rows."},
                        {"type": "image_url", "image_url": {"url": data_url}},
                    ],
                },
            ],
            models=VISION_MODELS,
            temperature=0.2,
            parser=_parse_llm_json,
        )
    if result is None:
        log.error("mutation_ocr_all_models_failed")
    return result


async def parse_mutation_text(text: str) -> MutationExtraction | None:
    """Varian untuk mutasi hasil ekspor CSV/teks (tanpa gambar)."""
    if not text.strip():
        return None
    # Batasi supaya tidak mengirim file raksasa ke LLM.
    trimmed = text[:20000]
    return await call_llm(
        [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {
                "role": "user",
                "content": (
                    "Extract every mutation row from this bank statement export. "
                    "Columns are usually date, description, amount, direction.\n\n"
                    f"{trimmed}"
                ),
            },
        ],
        models=VISION_MODELS,
        temperature=0.0,
        parser=_parse_llm_json,
    )


# ── PDF ───────────────────────────────────────────────────────────────────────


def is_pdf_upload(
    data: bytes,
    *,
    mime_type: str | None = None,
    filename: str | None = None,
) -> bool:
    """Deteksi PDF dari magic bytes, MIME type, atau ekstensi nama file."""
    if data[: len(PDF_MAGIC)] == PDF_MAGIC:
        return True
    if (mime_type or "").lower().split(";")[0].strip() in PDF_MIME_TYPES:
        return True
    return (filename or "").lower().endswith(PDF_EXTENSIONS)


def extract_pdf_text(data: bytes) -> str:
    """Teks dari seluruh halaman PDF ('' bila PDF hasil scan tanpa layer teks)."""
    if fitz is None or not data:
        return ""
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            return "\n".join(page.get_text("text") for page in doc)
    except Exception as exc:  # noqa: BLE001 - PDF korup tidak boleh bikin 500
        log.warning("mutation_pdf_text_failed", error=str(exc))
        return ""


def render_pdf_pages(data: bytes) -> Iterator[bytes]:
    """Yield PNG bytes per halaman PDF, satu per satu.

    Lazy: hanya satu halaman berada di memori pada satu waktu, dan PDF yang
    gagal dirender sebagian tetap mengembalikan halaman yang sudah berhasil.
    """
    if fitz is None or not data:
        return
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            for page in doc:
                pixmap = page.get_pixmap(dpi=PDF_RENDER_DPI)
                yield pixmap.tobytes("png")
    except Exception as exc:  # noqa: BLE001 - PDF korup tidak boleh bikin 500
        log.warning("mutation_pdf_render_failed", error=str(exc))
        return


async def parse_mutation_pdf(data: bytes) -> MutationExtraction | None:
    """Ekstrak mutasi dari PDF e-statement.

    Dua jalur: (a) PDF digital punya layer teks → jalur teks (cepat, murah,
    akurat); (b) PDF hasil scan → tiap halaman di-render ke PNG lalu dibaca
    vision LLM, hasil semua halaman digabung. Jumlah halaman tidak dibatasi.
    """
    if not data:
        return None

    text = extract_pdf_text(data)
    if len(" ".join(text.split())) >= MIN_PDF_TEXT_CHARS:
        return await parse_mutation_text(text)

    merged: MutationExtraction | None = None
    pages = 0
    for png in render_pdf_pages(data):
        pages += 1
        page_result = await parse_mutation_image(png, "image/png")
        if page_result is None:
            continue
        if merged is None:
            merged = page_result
            continue
        if merged.account_hint is None:
            merged.account_hint = page_result.account_hint
        merged.mutations.extend(page_result.mutations)

    if pages == 0:
        log.error("mutation_pdf_no_content")
        return None
    if merged is None:
        log.error("mutation_pdf_all_pages_failed", pages=pages)
    else:
        log.info("mutation_pdf_ok", pages=pages, scanned=True)
    return merged


# ── Pencocokan ────────────────────────────────────────────────────────────────


class MatchPair(BaseModel):
    mutation: ParsedMutation
    transaction_id: str
    transaction_type: str
    transaction_amount: str
    transaction_date: str
    transaction_merchant: str | None
    day_diff: int
    amount_diff: str


def fallback_category_id(db: Session, user_id: uuid.UUID, category_type: str) -> uuid.UUID:
    """Kategori fallback untuk pending_transaction (kolomnya NOT NULL).

    Ambil kategori default (milik user atau global) bertipe sama; diurutkan
    agar kategori default menang lebih dulu."""
    stmt = (
        select(Category)
        .where(
            Category.type == category_type,
            category_visible_clause(user_id),
        )
        .order_by(Category.is_default.desc(), Category.name.asc())
    )
    category = db.scalars(stmt).first()
    if category is None:
        raise ValueError(f"tidak ada kategori tipe '{category_type}' untuk user ini")
    return category.id


def find_matches(
    db: Session,
    *,
    user_id: uuid.UUID,
    mutations: list[ParsedMutation],
    account_id: uuid.UUID | None,
    amount_tolerance: Decimal = DEFAULT_AMOUNT_TOLERANCE,
    date_window_days: int = DEFAULT_DATE_WINDOW_DAYS,
) -> tuple[list[MatchPair], list[ParsedMutation], list[Transaction]]:
    """
    Cocokkan mutasi bank dengan transaksi tercatat.

    Aturan:
      - debit  → kandidat: expense, atau transfer KELUAR dari akun terpilih
      - credit → kandidat: income, atau transfer MASUK ke akun terpilih
      - |nominal mutasi - nominal transaksi| ≤ amount_tolerance
      - |tanggal mutasi - tanggal transaksi| ≤ date_window_days
      - akun sama bila `account_id` dipilih user

    Setiap transaksi hanya boleh dipakai sekali (greedy: mutasi dengan
    kandidat paling dekat tanggalnya & selisih nominal terkecil menang).

    Return: (matches, mutasi tanpa pasangan, transaksi dalam rentang tanpa
    pasangan).
    """
    if not mutations:
        return [], [], []

    dated = [m for m in mutations if m.date]
    if dated:
        parsed = [date.fromisoformat(m.date) for m in dated]
        window_start = min(parsed) - timedelta(days=date_window_days)
        window_end = max(parsed) + timedelta(days=date_window_days + 1)
        lower = datetime.combine(window_start, datetime.min.time(), tzinfo=UTC)
        upper = datetime.combine(window_end, datetime.min.time(), tzinfo=UTC)
    else:
        lower = datetime.now(UTC) - timedelta(days=90)
        upper = datetime.now(UTC) + timedelta(days=1)

    stmt = select(Transaction).where(
        Transaction.user_id == user_id,
        Transaction.transaction_date >= lower,
        Transaction.transaction_date < upper,
    )
    if account_id is not None:
        # Sertakan transfer yang MASUK ke akun ini (to_account_id) supaya mutasi
        # kredit hasil transfer antarakun bisa dicocokkan.
        stmt = stmt.where(
            (Transaction.account_id == account_id) | (Transaction.to_account_id == account_id)
        )
    txs = list(db.scalars(stmt.order_by(Transaction.transaction_date.asc())))

    used: set[uuid.UUID] = set()
    matches: list[MatchPair] = []
    unmatched: list[ParsedMutation] = []

    for mutation in mutations:
        candidates: list[tuple[int, Decimal, Transaction]] = []
        mutation_day = date.fromisoformat(mutation.date) if mutation.date else None
        for tx in txs:
            if tx.id in used or not _direction_matches(mutation, tx, account_id):
                continue
            amount_diff = abs(Decimal(tx.total_amount) - mutation.amount)
            if amount_diff > amount_tolerance:
                continue
            day_diff = 0
            if mutation_day is not None:
                tx_day = tx.transaction_date.date()
                day_diff = abs((tx_day - mutation_day).days)
                if day_diff > date_window_days:
                    continue
            candidates.append((day_diff, amount_diff, tx))

        if not candidates:
            unmatched.append(mutation)
            continue

        # Paling dekat tanggalnya, lalu selisih nominal terkecil.
        candidates.sort(key=lambda item: (item[0], item[1]))
        day_diff, amount_diff, tx = candidates[0]
        used.add(tx.id)
        matches.append(
            MatchPair(
                mutation=mutation,
                transaction_id=str(tx.id),
                transaction_type=tx.type,
                transaction_amount=str(Decimal(tx.total_amount)),
                transaction_date=tx.transaction_date.isoformat(),
                transaction_merchant=tx.merchant,
                day_diff=day_diff,
                amount_diff=str(amount_diff),
            )
        )

    unmatched_txs = [tx for tx in txs if tx.id not in used]
    # Hanya transaksi dalam rentang tanggal mutasi yang relevan untuk dilaporkan
    # "belum ada di mutasi" — hindari membanjiri user dengan transaksi lama.
    if dated:
        unmatched_txs = [
            tx for tx in unmatched_txs if min(parsed) <= tx.transaction_date.date() <= max(parsed)
        ]
    return matches, unmatched, unmatched_txs


def _direction_matches(mutation: ParsedMutation, tx: Transaction, account_id) -> bool:
    if mutation.direction == "debit":
        if tx.type == "expense":
            return True
        # Transfer keluar dari akun yang diunggah.
        return tx.type == "transfer" and (account_id is None or tx.account_id == account_id)
    if tx.type == "income":
        return True
    return tx.type == "transfer" and (account_id is None or tx.to_account_id == account_id)


def resolve_upload_account(
    db: Session,
    *,
    user_id: uuid.UUID,
    account_id: uuid.UUID | None,
    account_hint: str | None,
) -> uuid.UUID | None:
    """Tentukan akun mutasi: pilihan user → hint nama dari statement → None."""
    if account_id is not None:
        return account_id
    if not account_hint:
        return None
    hint = account_hint.strip().lower()
    accounts = db.scalars(
        select(Account).where(Account.user_id == user_id, Account.is_active.is_(True))
    ).all()
    for account in accounts:
        name = account.account_name.lower()
        if hint in name or name in hint:
            return account.id
    return None
