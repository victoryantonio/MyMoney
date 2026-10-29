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
import csv
import html
import json
import re
import uuid
from collections import Counter
from collections.abc import Iterator
from dataclasses import dataclass, field
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

from app.core.llm_client import TEXT_MODELS, VISION_MODELS, call_llm
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
- Many Indonesian e-statements (SeaBank, BCA, Mandiri, …) split amounts into
  TWO columns, "Keluar" and "Masuk". Use whichever one is filled for that row;
  never add them together and never swap them.
- The rightmost numeric column is usually the running balance (Saldo Akhir) —
  never use it as `amount`. Skip Saldo Awal / Saldo Akhir / total rows.
- Dates often omit the year (e.g. "01 SEP"); infer it from the statement
  period printed on the page (e.g. "01 SEP 2026 sampai 30 SEP 2026" → 2026).
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

_TEXT_SYSTEM_PROMPT = """You are a bank statement (mutasi rekening) reader for
the 'MyMoney' app. You receive the PLAIN TEXT of a bank statement (PDF text
layer, CSV export, or copy-paste). Extract EVERY transaction row into JSON.

Respond ONLY with a valid JSON object, no markdown, no backticks, no
explanations.
Schema:
{
  "account_hint": string or null (bank name if visible, e.g. "SeaBank"),
  "mutations": [
    {
      "date": string "yyyy-mm-dd" (null if not visible),
      "time": string "HH:MM" (null if not visible),
      "description": string (as printed),
      "amount": number (positive, thousands separators removed),
      "direction": "debit" or "credit"
    }
  ]
}

Rules:
- `debit` = money LEAVING the account (Keluar / DB / DEBET / -).
- `credit` = money ENTERING the account (Masuk / CR / KREDIT / +).
- Statements often split amounts into TWO columns, "Keluar" and "Masuk".
  Use whichever one is filled; never add them together.
- The rightmost numeric column is usually the running balance (Saldo) — it is
  NEVER the transaction amount. Never emit Saldo Awal / Saldo Akhir / totals.
- Dates may omit the year (e.g. "01 SEP"); infer it from the statement period
  (e.g. "Periode Mutasi: 01 SEP 2026 sampai 30 SEP 2026" → 2026).
- Descriptions may be truncated by the bank; copy them as printed.
- `amount` is always positive; the SIGN is expressed by `direction`.
- If the currency uses a decimal comma and dot thousands ("1.250.000,50"),
  interpret dot as thousands and comma as decimal.
- Skip rows you cannot read confidently rather than guessing a number.
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
        raw_amount = row.get("amount")
        amount = _to_decimal(raw_amount)
        direction = _normalize_direction(row.get("direction"), raw_amount)
        if direction is None or amount is None or amount <= 0:
            # Sebagian model mengembalikan kolom terpisah, bukan `amount` +
            # `direction` (mis. {"debit": 18000, "credit": null}). Pakai itu
            # agar baris tidak hilang hanya karena bentuk JSON berbeda.
            debit_amount = _to_decimal(row.get("debit"))
            credit_amount = _to_decimal(row.get("credit"))
            has_debit = debit_amount is not None and debit_amount > 0
            has_credit = credit_amount is not None and credit_amount > 0
            if has_debit != has_credit:  # tepat satu kolom terisi
                amount = abs(debit_amount if has_debit else credit_amount)
                direction = "debit" if has_debit else "credit"
        if direction is None or amount is None or amount <= 0:
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


_MONTH_ABBREV = {
    "jan": 1,
    "januari": 1,
    "feb": 2,
    "februari": 2,
    "peb": 2,
    "mar": 3,
    "maret": 3,
    "apr": 4,
    "april": 4,
    "may": 5,
    "mei": 5,
    "jun": 6,
    "juni": 6,
    "jul": 7,
    "juli": 7,
    "aug": 8,
    "agu": 8,
    "ags": 8,
    "agustus": 8,
    "sep": 9,
    "sept": 9,
    "september": 9,
    "oct": 10,
    "okt": 10,
    "oktober": 10,
    "nov": 11,
    "november": 11,
    "dec": 12,
    "des": 12,
    "desember": 12,
}


def _normalize_date(value, default_year: int | None = None) -> str | None:
    """Normalisasi tanggal dari LLM/statement → ISO yyyy-mm-dd.

    Mendukung ISO, dd-mm-yyyy, dd/mm/yyyy, serta `01 SEP` / `01 Sep 2026`
    (e-statement Indonesia sering menghilangkan tahun karena sudah tercantum
    di periode mutasi — `default_year` mengisinya).
    """
    if value is None:
        return None
    text = re.sub(r"\s+", " ", str(value).strip())
    if not text:
        return None

    match = re.match(r"^(\d{4})-(\d{1,2})-(\d{1,2})", text)
    if match:
        year, month, day = match.groups()
        text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
    else:
        match = re.match(r"^(\d{1,2})[/-](\d{1,2})[/-](\d{2,4})$", text)
        if match:
            day, month, year = match.groups()
            year = year if len(year) == 4 else f"20{year}"
            text = f"{year}-{month.zfill(2)}-{day.zfill(2)}"
        else:
            match = re.match(r"^(\d{1,2})[/-](\d{1,2})$", text)
            if match:
                day, month = match.groups()
                if default_year is None:
                    return None
                text = f"{default_year:04d}-{month.zfill(2)}-{day.zfill(2)}"
            else:
                match = re.match(r"^(\d{1,2})[\s-]+([A-Za-z]{3,})\.?,?[\s-]*(\d{2,4})?$", text)
                if not match:
                    return None
                day, month_name, year = match.groups()
                month = _MONTH_ABBREV.get(month_name.lower().rstrip("."))
                resolved_year = int(year) if year else default_year
                if month is None or resolved_year is None:
                    return None
                if len(year or "") == 2:
                    resolved_year += 2000
                text = f"{resolved_year:04d}-{month:02d}-{int(day):02d}"

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


# ── Parser deterministik (CSV / teks tabel / e-statement PDF) ─────────────────
#
# Jauh lebih murah, cepat, dan konsisten daripada memanggil LLM. Dipakai lebih
# dulu untuk berkas yang punya layer teks; LLM hanya fallback bila format tabel
# tidak dikenali (mis. PDF hasil scan atau tata letak yang tidak lazim).

_DATE_HEADERS = ("tanggal", "date", "tgl")
_DESC_HEADERS = ("keterangan", "description", "uraian", "remark", "transaksi")
_DEBIT_HEADERS = ("keluar", "debit", "debet", "pengeluaran", "out")
_CREDIT_HEADERS = ("masuk", "kredit", "pemasukan", "in")
_AMOUNT_HEADERS = ("nominal", "amount", "jumlah", "nilai")
# Satu kolom nominal yang arahnya ditandai akhiran DB/CR di sebelah angka
# (format BCA lama: TANGGAL | KETERANGAN | CBG | MUTASI | SALDO).
_FLOW_HEADERS = ("mutasi",)
_BALANCE_HEADERS = ("saldo", "balance")

# Baris halaman/administratif yang tidak boleh ikut menjadi deskripsi.
_NOISE_LINE_RE = re.compile(
    r"^(halaman|bersambung|catatan|rekening|s/n|periode|mata\s+uang"
    r"|no\.?\s*rekening|nomor\s+rekening|nama\s+pemilik|informasi\s+rekening"
    r"|ringkasan|total|tabungan\s*-\s*rincian|disclaimer)",
    re.IGNORECASE,
)

# `01  OCT  2026` — tanggal cetak, bukan keterangan transaksi.
_MONTH_YEAR_LINE_RE = re.compile(r"^\d{1,2}\s+[A-Za-z]{3,9}\.?\s+\d{4}$")

# Baris ringkasan/rekening, bukan transaksi.
_SUMMARY_PREFIXES = (
    "saldo awal",
    "saldo akhir",
    "total transaksi",
    "total keluar",
    "total masuk",
    "periode mutasi",
    "informasi rekening",
    "nama pemilik",
    "nomor rekening",
    "ringkasan",
    "mutasi rekening",
    "mutasi cr",
    "mutasi db",
)

_EMPTY_CELLS = {"", "-", "–", "—", ".", "0", "0,00", "0.00"}


@dataclass(frozen=True)
class _ColumnMap:
    """Pemetaan kolom statement → indeks sel."""

    date: int | None = None
    description: int | None = None
    debit: int | None = None
    credit: int | None = None
    flow: int | None = None
    amount: int | None = None
    balance: int | None = None


def _header_role(cell: str) -> str | None:
    """Peran sebuah sel header (date/description/debit/credit/...)."""
    words = re.sub(r"[^a-z ]", " ", cell.lower()).split()
    if not words:
        return None
    for role, headers in (
        ("balance", _BALANCE_HEADERS),
        ("debit", _DEBIT_HEADERS),
        ("credit", _CREDIT_HEADERS),
        ("amount", _AMOUNT_HEADERS),
        ("flow", _FLOW_HEADERS),
        ("date", _DATE_HEADERS),
        ("description", _DESC_HEADERS),
    ):
        for header in headers:
            if all(word in words for word in header.split()):
                return role
    return None


def _detect_year(text: str) -> int | None:
    """Tahun dari periode statement (yang paling sering muncul menang)."""
    # `PERIODE : SEPTEMBER 2026` / `Periode Mutasi: 01 SEP 2026 sampai ...`
    period = re.search(r"periode[^\n]*?(20\d{2})", text, re.IGNORECASE) or re.search(
        r"(20\d{2})[^\n]{0,20}(?:sampai|s/d|-)\s*\d{1,2}\b", text, re.I
    )
    if period:
        return int(period.group(1))
    years = re.findall(r"\b(20\d{2})\b", text)
    if not years:
        return None
    return int(Counter(years).most_common(1)[0][0])


_KNOWN_BANKS = (
    "SeaBank",
    "BCA",
    "Mandiri",
    "BNI",
    "BRI",
    "CIMB",
    "Permata",
    "Danamon",
    "BSI",
    "BTN",
    "Jenius",
    "Jago",
    "GoPay",
    "OVO",
    "DANA",
    "ShopeePay",
)


def _detect_account_hint(text: str) -> str | None:
    """Nama bank dari statement (untuk memilih akun secara otomatis).

    Sengaja hanya menerima nama bank yang dikenal atau baris `Bank: <nama>`.
    Pola lama bisa mengembalikan nomor rekening atau teks pemasaran (mis.
    `NO. REKENING  SEABANK: 901046266356   Hubungi kami`) sehingga akun tidak
    pernah ketemu saat pencocokan.
    """
    labelled = re.search(
        r"^\s*\*?\s*(?:nama\s+)?bank\s*[:：]\s*(?P<name>[^\n]{2,40})$",
        text,
        re.IGNORECASE | re.MULTILINE,
    )
    if labelled:
        name = labelled.group("name").strip(" *\t")
        if name and not re.match(r"^[\d\W]+$", name):
            return name[:100]
    # Nama bank penerbit muncul paling sering. Menghitung kemunculan mencegah
    # statement Permata dikenali sebagai SeaBank hanya karena ada satu baris
    # transfer "PT BANK SEABANK INDONESIA" di keterangan transaksi.
    best_bank: str | None = None
    best_count = 0
    for bank in _KNOWN_BANKS:
        count = len(re.findall(rf"(?<![A-Za-z]){re.escape(bank)}(?![A-Za-z])", text, re.IGNORECASE))
        if count > best_count:
            best_bank = bank
            best_count = count
    return best_bank


def _clean_description(value: str) -> str:
    """Rapikan deskripsi: dekode entitas HTML text layer, buang spasi ganda."""
    text = html.unescape(str(value or ""))
    text = text.replace("\u00a0", " ")
    text = re.sub(r"\s+", " ", text).strip(" -:\t")
    return text[:200]


def _is_summary_row(description: str) -> bool:
    text = description.strip().lower()
    return any(text.startswith(prefix) for prefix in _SUMMARY_PREFIXES)


_SUFFIX_RE = re.compile(r"[ \t]{1,3}(DB|CR|D|K|DR|KR)\.?(?![A-Za-z])", re.IGNORECASE)


def _suffix_direction(text: str, end: int) -> str | None:
    """Arah dana dari akhiran `DB`/`CR` tepat setelah token nominal."""
    match = _SUFFIX_RE.match(text, end)
    if not match:
        return None
    return "debit" if match.group(1).upper() in ("DB", "D", "DR") else "credit"


def _cell_amount(cell: str | None) -> Decimal | None:
    """Nominal absolut dari satu sel; None untuk sel kosong/nol."""
    if cell is None:
        return None
    text = str(cell).strip()
    suffix = re.search(r"[ \t]+(DB|CR|D|K|DR|KR)\.?$", text, re.IGNORECASE)
    if suffix:
        text = text[: suffix.start()].strip()
    if text.lower() in _EMPTY_CELLS:
        return None
    negative = text.startswith("-") or (text.startswith("(") and text.endswith(")"))
    value = _to_decimal(text.replace("(", "").replace(")", ""))
    if value is None or value == 0:
        return None
    return -abs(value) if negative else abs(value)


def _direction_from_description(description: str) -> str | None:
    """Arah dana dari kata kunci transaksi (fallback kolom tunggal tanpa DB/CR)."""
    text = re.sub(r"\s+", " ", description.lower()).strip()
    if not text:
        return None
    # `KARTU KREDIT/PL` adalah pembayaran (debit), bukan transaksi kredit.
    if text.startswith("kartu"):
        return "debit"
    if re.search(r"\b(?:debet|debit)\b", text):
        return "debit"
    if text.startswith(("setoran", "bunga", "transfer masuk", "penarikan tunai")):
        return "credit" if not text.startswith("penarikan") else "debit"
    if re.search(r"\b(?:kredit|kr|cr)\b", text):
        return "credit"
    if text.startswith(("biaya", "tarikan", "pembayaran")):
        return "debit"
    return None


def _statement_lines(text: str) -> list[str]:
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def _detect_delimiter(lines: list[str]) -> str | None:
    for delimiter in ("|", "\t", ";"):
        if sum(1 for line in lines if delimiter in line) >= 2:
            return delimiter
    # Koma hanya dipakai bila polanya benar-benar tabular. Koma di antara angka
    # (`159,227.00`) adalah pemisah ribuan Indonesia, bukan pemisah kolom.
    if sum(1 for line in lines if len(re.findall(r"(?<!\d),(?!\d)", line)) >= 3) >= 2:
        return ","
    return None


def _split_row(line: str, delimiter: str) -> list[str]:
    try:
        cells = next(csv.reader([line], delimiter=delimiter, skipinitialspace=True))
    except csv.Error:
        cells = line.split(delimiter)
    cells = [cell.strip() for cell in cells]
    while cells and not cells[0]:
        cells.pop(0)
    while cells and not cells[-1]:
        cells.pop()
    return cells


def _find_header(cells: list[str]) -> _ColumnMap | None:
    """Deteksi baris header → pemetaan kolom. None bila bukan header."""
    roles: dict[str, int] = {}
    for index, cell in enumerate(cells):
        role = _header_role(cell)
        if role and role not in roles:
            roles[role] = index
    if "description" not in roles and "date" not in roles:
        return None
    if not ({"debit", "credit", "flow", "amount"} & roles.keys()):
        return None
    return _ColumnMap(**roles)


def _row_to_mutation(
    cells: list[str], columns: _ColumnMap, default_year: int | None
) -> ParsedMutation | None:
    def cell(index: int | None) -> str:
        if index is None or index >= len(cells):
            return ""
        return cells[index]

    debit = _cell_amount(cell(columns.debit))
    credit = _cell_amount(cell(columns.credit))
    if debit is not None and credit is not None:
        return None  # dua arah terisi sekaligus → tidak bisa dipastikan
    if debit is not None:
        amount, direction = debit, "debit"
    elif credit is not None:
        amount, direction = credit, "credit"
    elif columns.flow is not None:
        raw_flow = cell(columns.flow)
        flow = _cell_amount(raw_flow)
        if flow is None:
            return None
        suffix = re.search(r"(DB|CR|D|K|DR|KR)\.?\s*$", raw_flow, re.IGNORECASE)
        if suffix:
            direction = "debit" if suffix.group(1).upper() in {"DB", "D", "DR"} else "credit"
        else:
            direction = _direction_from_description(cell(columns.description))
            if direction is None:
                direction = "debit"  # BCA lama: nominal tanpa akhiran = keluar
        amount = flow
    elif columns.amount is not None:
        raw = _cell_amount(cell(columns.amount))
        if raw is None:
            return None
        amount, direction = abs(raw), ("debit" if raw < 0 else "credit")
    else:
        return None

    description = _clean_description(cell(columns.description))
    if not description or _is_summary_row(description):
        return None

    return ParsedMutation(
        date=_normalize_date(cell(columns.date), default_year=default_year),
        time=None,
        description=description[:200],
        amount=amount,
        direction=direction,
    )


def _parse_delimited_statement(text: str, delimiter: str) -> list[ParsedMutation]:
    default_year = _detect_year(text)
    columns: _ColumnMap | None = None
    parsed: list[ParsedMutation] = []
    for line in _statement_lines(text):
        if not line.strip():
            continue
        cells = _split_row(line, delimiter)
        header = _find_header(cells)
        if header is not None:
            columns = header
            continue
        if columns is None:
            continue
        if all(re.fullmatch(r"[-: ]*", cell) for cell in cells):
            continue  # baris pemisah markdown (|---|---|)
        row = _row_to_mutation(cells, columns, default_year)
        if row is not None:
            parsed.append(row)
    return parsed


def _role_spans(line: str) -> dict[str, tuple[int, int]]:
    """Posisi karakter tiap kolom pada header bertata letak spasi (PDF text layer)."""
    spans: dict[str, tuple[int, int]] = {}
    for match in re.finditer(r"[A-Za-z]+", line):
        role = _header_role(match.group())
        if role and role not in spans:
            spans[role] = (match.start(), match.end())
    return spans


_LEADING_DATE_RE = re.compile(
    r"^\s*(?P<date>"
    r"\d{4}-\d{2}-\d{2}"
    r"|\d{1,2}[/-]\d{1,2}[/-]\d{2,4}"
    r"|\d{1,2}[/-]\d{1,2}(?![/-])"  # dd/mm tanpa tahun (tahun dari PERIODE)
    # `01 SEP` / `01 Sep 2026` — pemisah tahun harus satu spasi agar kolom
    # nominal yang jauh di kanan (mis. `01 SEP       119`) tidak ikut tertelan.
    r"|\d{1,2}\s+[A-Za-z]{3,}\.?(?:\s(?:\d{4}|\d{2}))?"
    r")\s+(?P<rest>.*)$"
)
_NUM_TOKEN_RE = re.compile(r"(?<![\w.])(-?\d[\d.,]*)(?![\w.])")
_AMOUNT_ROLES = ("debit", "credit", "flow")


@dataclass(frozen=True)
class _AmountToken:
    """Token nominal pada satu baris beserta arah dari akhiran DB/CR."""

    start: int
    end: int
    value: Decimal
    direction: str | None = None


def _amount_tokens(line: str, start: int) -> list[_AmountToken]:
    """Semua token nominal pada baris setelah offset tertentu.

    Dulu hanya token yang bersambung di akhir baris yang diambil; akibatnya
    baris dengan kolom `Masuk` di tengah (lalu kolom saldo di kanan) tidak
    pernah terbaca.
    """
    tokens: list[_AmountToken] = []
    for match in _NUM_TOKEN_RE.finditer(line, start):
        value = _cell_amount(match.group(1))
        if value is None:
            continue
        tokens.append(
            _AmountToken(
                start=match.start(),
                end=match.end(),
                value=value,
                direction=_suffix_direction(line, match.end()),
            )
        )
    return tokens


def _match_role(start: int, end: int, spans: dict[str, tuple[int, int]]) -> str | None:
    """Kolom yang paling banyak beririsan dengan sebuah token nominal.

    Kolom angka umumnya rata kanan, jadi token bisa mulai di sebelah kiri
    judul kolomnya — tumpang-tindih karakter lebih andal daripada titik awal.
    """
    best_role: str | None = None
    best_overlap = 0
    for role, (role_start, role_end) in spans.items():
        overlap = min(end, role_end) - max(start, role_start)
        if overlap > best_overlap:
            best_role, best_overlap = role, overlap
    if best_role is not None:
        return best_role
    # Tidak beririsan sama sekali → pakai kolom terdekat di sebelah kiri.
    nearest: str | None = None
    nearest_start = -1
    for role, (role_start, _role_end) in spans.items():
        if role_start <= start and role_start > nearest_start:
            nearest, nearest_start = role, role_start
    return nearest


@dataclass
class _RowBuffer:
    """Baris mutasi yang dirakit dari beberapa baris teks.

    E-statement Indonesia memecah satu transaksi menjadi beberapa baris fisik:

    * SeaBank: `NASI PINDANG` (di atas) → `01 SEP  KUDUS "BU  18.000` →
      `Pembayaran` (di bawah);
    * BCA: `01/09  KARTU KREDIT/PL  0831 ...  159,227.00 DB` → beberapa baris
      keterangan lanjutan di bawahnya.

    `pre` = baris di atas baris tanggal, `inline` = teks pada baris tanggal,
    `post` = baris lanjutan di bawahnya.
    """

    date: str | None = None
    pre: list[str] = field(default_factory=list)
    inline: list[str] = field(default_factory=list)
    post: list[str] = field(default_factory=list)
    amount: Decimal | None = None
    direction: str | None = None
    post_limit: int = 0

    def is_complete(self) -> bool:
        return self.amount is not None and self.direction is not None

    def accepts_post(self) -> bool:
        return len(self.post) < self.post_limit

    def to_mutation(self) -> ParsedMutation | None:
        # Label jenis transaksi ("Pembayaran", "Transfer") dicetak DI BAWAH
        # baris tanggal, jadi ditaruh paling depan agar deskripsi terbaca.
        if self.post_limit == 1:
            parts = [*self.post, *self.pre, *self.inline]
        else:
            parts = [*self.inline, *self.post, *self.pre]
        description = _join_parts(parts)
        if not self.is_complete() or not description or _is_summary_row(description):
            return None
        return ParsedMutation(
            date=self.date,
            time=None,
            description=description,
            amount=self.amount,
            direction=self.direction,
        )


def _join_parts(parts: list[str]) -> str:
    """Gabungkan potongan keterangan, buang kata yang berulang.

    Baris `Bunga Tabungan` di atas dan `Bunga` di bawah menghasilkan
    `Bunga Tabungan`, bukan `Bunga Bunga Tabungan`.
    """
    words: list[str] = []
    seen: set[str] = set()
    for part in parts:
        for word in _clean_description(part).split(" "):
            key = re.sub(r"[^0-9a-z]", "", word.lower())
            if not key or key in seen:
                continue
            seen.add(key)
            words.append(word)
    return _clean_description(" ".join(words))


def _text_candidate(line: str) -> str | None:
    """Teks pada baris tanpa tanggal — kandidat keterangan transaksi.

    Baris buangan (header halaman, footer, disclaimer) ditolak agar tidak ikut
    menempel ke transaksi berikutnya.
    """
    text = _clean_description(line)
    if len(text) < 2 or not re.search(r"[A-Za-z]{2,}", text):
        return None
    if _MONTH_YEAR_LINE_RE.match(text):
        return None
    if _NOISE_LINE_RE.match(text) or _is_summary_row(text):
        return None
    return text


def _parse_whitespace_statement(text: str) -> list[ParsedMutation]:
    """Parser text layer PDF yang kolomnya dipisah spasi.

    Mendukung dua varian tata letak:
      * dua kolom nominal (`Keluar` + `Masuk`, mis. SeaBank) — keterangan
        merchant dicetak satu baris DI ATAS baris tanggal dan label jenis
        transaksi satu baris DI BAWAHNYA;
      * satu kolom nominal (`Mutasi` dengan akhiran DB/CR, mis. BCA) —
        keterangan ada pada baris tanggal itu sendiri dan berlanjut ke bawah.
    """
    default_year = _detect_year(text)
    spans: dict[str, tuple[int, int]] | None = None
    description_col = 0
    two_columns = False
    parsed: list[ParsedMutation] = []
    buffer: _RowBuffer | None = None
    pending_text: str | None = None

    def flush() -> None:
        nonlocal buffer
        if buffer is not None:
            row = buffer.to_mutation()
            if row is not None:
                parsed.append(row)
            buffer = None

    for line in _statement_lines(text):
        if not line.strip():
            continue

        found = _role_spans(line)
        if (
            len(found) >= 2
            and set(_AMOUNT_ROLES) & found.keys()
            and not _LEADING_DATE_RE.match(line)
        ):
            spans = found
            two_columns = "debit" in found or "credit" in found
            description_col = found.get("description", (0, 0))[0]
            flush()
            pending_text = None
            continue
        if spans is None:
            continue

        leading = _LEADING_DATE_RE.match(line)
        if not leading:
            candidate = _text_candidate(line)
            if candidate is None:
                plain = _clean_description(line)
                if plain and (_NOISE_LINE_RE.match(plain) or _is_summary_row(plain)):
                    # Baris administratif = batas halaman/ringkasan.
                    flush()
                    pending_text = None
                continue
            indent = len(line) - len(line.lstrip())
            if buffer is not None and buffer.accepts_post() and indent >= description_col:
                buffer.post.append(candidate)
            else:
                pending_text = candidate
            continue

        flush()
        rest = leading.group("rest")
        offset = leading.start("rest")
        tokens = _amount_tokens(line, offset)

        sides: list[_AmountToken] = []
        sides_roles: list[str] = []
        first_amount_start: int | None = None
        for token in tokens:
            role = _match_role(token.start, token.end, spans)
            if role not in _AMOUNT_ROLES:
                continue
            if first_amount_start is None:
                first_amount_start = token.start - offset
            sides.append(token)
            sides_roles.append(role)
        if len(sides) != 1:
            # Dua arah terisi sekaligus atau kolom tidak jelas → jangan menebak.
            pending_text = None
            continue

        token = sides[0]
        role = sides_roles[0]
        raw_description = rest[: first_amount_start if first_amount_start is not None else 0]
        description = _clean_description(raw_description)

        if role in ("debit", "credit"):
            direction: str | None = role
        else:  # kolom tunggal `Mutasi`
            direction = token.direction or _direction_from_description(
                f"{pending_text or ''} {description}"
            )
            if direction is None:
                # BCA: baris masuk dicetak tanpa akhiran, hanya debit diberi `DB`.
                direction = "credit"

        buffer = _RowBuffer(
            date=_normalize_date(leading.group("date"), default_year=default_year),
            amount=token.value,
            direction=direction,
            post_limit=1 if two_columns else 3,
        )
        if two_columns and pending_text:
            # Dua kolom nominal: nama merchant dicetak di baris di atas.
            buffer.pre.append(pending_text)
        if description:
            buffer.inline.append(description)
        pending_text = None

    flush()
    return parsed


def parse_statement_text(text: str) -> list[ParsedMutation]:
    """Parse mutasi dari teks tabel/CSV tanpa LLM.

    Mendukung tabel pipe/markdown, CSV/TSV/`;`, dan text layer PDF yang
    kolomnya dipisah spasi (butuh baris header Keluar/Masuk/Saldo).
    Mengembalikan list kosong bila format tidak dikenali → pemanggil memakai
    fallback LLM.
    """
    if not text.strip():
        return []
    delimiter = _detect_delimiter(_statement_lines(text))
    if delimiter is not None:
        rows = _parse_delimited_statement(text, delimiter)
        if rows:
            return rows
    return _parse_whitespace_statement(text)


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
    """Parse mutasi dari teks (CSV, ekspor, atau text layer e-statement PDF).

    Parser deterministik dicoba lebih dulu — hasilnya sama setiap kali dijalankan
    dan tidak memanggil LLM. Bila formatnya tidak dikenali, teks dikirim ke model
    **teks** sebagai fallback.
    """
    if not text.strip():
        return None

    rows = parse_statement_text(text)
    if rows:
        log.info("mutation_text_parsed", rows=len(rows), via="deterministic")
        return MutationExtraction(
            account_hint=_detect_account_hint(text),
            mutations=rows,
        )

    # Batasi supaya tidak mengirim file raksasa ke LLM.
    trimmed = text[:20000]
    result = await call_llm(
        [
            {"role": "system", "content": _TEXT_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": f"Extract every mutation row from this bank statement text.\n\n{trimmed}",
            },
        ],
        models=TEXT_MODELS,
        temperature=0.0,
        parser=_parse_llm_json,
    )
    if result is None:
        log.error("mutation_text_all_models_failed")
    else:
        log.info("mutation_text_parsed", rows=len(result.mutations), via="llm")
    return result


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


def _layout_text(words) -> str:
    """Susun ulang baris teks dari kata + koordinat x (kolom tetap sejajar).

    Lebar karakter dan batas kiri dihitung sekali per halaman supaya pemetaan
    x → indeks karakter konsisten untuk header dan baris data (kalau dihitung
    per baris, kolom angka bisa bergeser dan tidak lagi sejajar dengan header).
    """
    items = [
        (float(item[0]), float(item[1]), float(item[2]), str(item[4]))
        for item in words
        if len(item) >= 5 and str(item[4]).strip()
    ]
    if not items:
        return ""

    left = min(item[0] for item in items)
    widths = [(x1 - x0) / len(word) for x0, _y0, x1, word in items if word]
    char_width = sorted(widths)[len(widths) // 2] if widths else 5.0
    char_width = min(max(char_width, 2.0), 20.0)

    lines: list[list[tuple[float, float, str]]] = []
    last_y: float | None = None
    for x0, y0, x1, word in sorted(items, key=lambda it: (it[1], it[0])):
        if last_y is None or abs(y0 - last_y) > 2.5:
            lines.append([])
            last_y = y0
        lines[-1].append((x0, x1, word))

    out: list[str] = []
    for line in lines:
        line.sort(key=lambda it: it[0])
        parts: list[str] = []
        cursor = 0
        for x0, _x1, word in line:
            target = int(round((x0 - left) / char_width))
            if target > cursor:
                parts.append(" " * (target - cursor))
                cursor = target
            elif cursor:
                parts.append(" ")
                cursor += 1
            parts.append(word)
            cursor += len(word)
        out.append("".join(parts).rstrip())
    return "\n".join(out)


def extract_pdf_text(data: bytes) -> str:
    """Teks dari seluruh halaman PDF ('' bila PDF hasil scan tanpa layer teks).

    Memakai koordinat kata (bukan spasi hasil ekstraksi biasa) supaya kolom
    tabel — Keluar/Masuk/Saldo — tetap sejajar dan bisa diurai deterministik.
    """
    if fitz is None or not data:
        return ""
    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            pages: list[str] = []
            for page in doc:
                try:
                    text = _layout_text(page.get_text("words"))
                except Exception:  # noqa: BLE001 - sebagian PDF tidak punya words
                    text = ""
                pages.append(text or page.get_text("text"))
            return "\n".join(pages)
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


# ── PDF: arah dana dari warna teks ────────────────────────────────────────────
#
# Sebagian bank tidak mencetak kolom Keluar/Masuk sama sekali: nominal masuk
# ditulis hijau dan nominal keluar merah (contoh: Permata lewat aplikasi
# PermataME). Text layer tetap memuat nominalnya, tetapi arah dana tidak
# tercetak sebagai teks — hanya sebagai warna. Jalur ini membaca warna span
# PDF sebelum jatuh ke parser teks/LLM, karena LLM pun tidak melihat warna
# ketika hanya diberi teks.

_CURRENCY_SPAN_RE = re.compile(r"^\s*(?:rp\.?|idr)\s*(?P<value>[\d.,]+)\s*$", re.IGNORECASE)
# Selisih kanal warna minimum agar sebuah span dianggap berwarna.
_COLOR_MIN_DELTA = 40
# Jarak vertikal maksimum keterangan → nominal (kelipatan tinggi baris).
_DESC_LINK_FACTOR = 3.0
# Span lebih panjang dari ini tidak mungkin berupa label tanggal.
_DATE_LABEL_MAX_CHARS = 20
# Baris keterangan bisa terpotong sehingga tahun berdiri sendiri ("2026").
_YEAR_ONLY_RE = re.compile(r"^(?:19|20)\d{2}$")


@dataclass(frozen=True)
class _PdfSpan:
    """Satu potongan teks PDF beserta posisi dan warnanya."""

    text: str
    x: float
    y: float
    height: float
    color: int

    @property
    def center(self) -> float:
        return self.y + self.height / 2


def _color_direction(color: int) -> str | None:
    """Arah dana dari warna teks: merah = keluar (debit), hijau = masuk (kredit)."""
    red = (color >> 16) & 0xFF
    green = (color >> 8) & 0xFF
    blue = color & 0xFF
    if red - min(green, blue) >= _COLOR_MIN_DELTA and red >= max(green, blue):
        return "debit"
    if green - min(red, blue) >= _COLOR_MIN_DELTA and green >= max(red, blue):
        return "credit"
    return None


def _page_spans(page) -> list[_PdfSpan]:
    """Semua span teks satu halaman PDF (kosong bila tanpa layer teks)."""
    spans: list[_PdfSpan] = []
    try:
        blocks = page.get_text("dict").get("blocks", [])
    except Exception:  # noqa: BLE001 - halaman rusak dilewati
        return spans
    for block in blocks:
        for line in block.get("lines", []):
            for span in line.get("spans", []):
                text = str(span.get("text", "")).strip()
                if not text:
                    continue
                bbox = span.get("bbox") or (0, 0, 0, 0)
                spans.append(
                    _PdfSpan(
                        text=text,
                        x=float(bbox[0]),
                        y=float(bbox[1]),
                        height=max(float(bbox[3]) - float(bbox[1]), 0.0),
                        color=int(span.get("color", 0)),
                    )
                )
    return spans


def _span_amount(span: _PdfSpan) -> tuple[Decimal, str] | None:
    """Nominal + arah dari span berwarna (`Rp 2,101,922.00` merah → debit)."""
    match = _CURRENCY_SPAN_RE.match(span.text)
    if not match:
        return None
    value = _cell_amount(match.group("value"))
    direction = _color_direction(span.color)
    if value is None or direction is None:
        return None
    return value, direction


def parse_colored_statement_pdf(data: bytes, text: str | None = None) -> list[ParsedMutation]:
    """Parse mutasi PDF yang arah dananya hanya ditandai warna teks.

    Keterangan dan nominal dikaitkan lewat kedekatan vertikal (satu transaksi =
    satu blok baris). Halaman dilewati bila ada nominal yang tidak berwarna,
    karena arah dana tidak boleh ditebak — pemanggil memakai parser teks biasa.
    """
    if fitz is None or not data:
        return []

    try:
        with fitz.open(stream=data, filetype="pdf") as doc:
            full_text = text if text is not None else extract_pdf_text(data)
            default_year = _detect_year(full_text)
            mutations: list[ParsedMutation] = []
            carried_date: str | None = None

            for page in doc:
                page_spans = _page_spans(page)
                if not page_spans:
                    continue

                amount_spans: list[tuple[_PdfSpan, Decimal, str]] = []
                labels: list[tuple[float, str]] = []
                label_ids: set[int] = set()
                skipped = False
                for span in page_spans:
                    amount = _span_amount(span)
                    if amount is not None:
                        amount_spans.append((span, *amount))
                        continue
                    if _CURRENCY_SPAN_RE.match(span.text):
                        # Nominal tanpa warna → arah dana tidak diketahui.
                        skipped = True
                        break
                    if len(span.text) <= _DATE_LABEL_MAX_CHARS:
                        row_date = _normalize_date(span.text, default_year=default_year)
                        if row_date:
                            labels.append((span.center, row_date))
                            label_ids.add(id(span))

                if skipped or not amount_spans:
                    continue

                ignored_ids = {id(span) for span, _value, _direction in amount_spans} | label_ids
                desc_spans = [
                    span
                    for span in page_spans
                    if id(span) not in ignored_ids
                    and len(span.text) >= 2
                    and (_YEAR_ONLY_RE.match(span.text) or _text_candidate(span.text) is not None)
                ]

                heights = sorted(span.height for span in page_spans if span.height > 0)
                line_height = heights[len(heights) // 2] if heights else 12.0
                max_gap = max(line_height * _DESC_LINK_FACTOR, 12.0)

                groups: dict[int, list[_PdfSpan]] = {
                    index: [] for index in range(len(amount_spans))
                }
                for span in desc_spans:
                    distance, index = min(
                        (abs(span.center - item[0].center), item_index)
                        for item_index, item in enumerate(amount_spans)
                    )
                    if distance <= max_gap:
                        groups[index].append(span)

                for index, (amount_span, value, direction) in enumerate(amount_spans):
                    row_date = next(
                        (
                            label_date
                            for label_y, label_date in reversed(labels)
                            if label_y <= amount_span.center
                        ),
                        None,
                    )
                    if row_date:
                        carried_date = row_date
                    parts = [
                        span.text
                        for span in sorted(groups[index], key=lambda item: (item.center, item.x))
                    ]
                    mutations.append(
                        ParsedMutation(
                            date=row_date or carried_date,
                            time=None,
                            description=_join_parts(parts) or "Mutasi",
                            amount=value,
                            direction=direction,
                        )
                    )

            if mutations:
                log.info("mutation_pdf_color_parsed", rows=len(mutations))
            return mutations
    except Exception as exc:  # noqa: BLE001 - PDF korup tidak boleh bikin 500
        log.warning("mutation_pdf_color_failed", error=str(exc))
        return []


async def parse_mutation_pdf(data: bytes) -> MutationExtraction | None:
    """Ekstrak mutasi dari PDF e-statement.

    Tiga jalur: (a) PDF digital yang arah dananya hanya dibedakan warna teks
    (mis. Permata: hijau = masuk, merah = keluar) → dibaca dari span berwarna;
    (b) PDF digital bertabel dengan kolom Keluar/Masuk → jalur teks; (c) PDF
    hasil scan → tiap halaman di-render ke PNG lalu dibaca vision LLM. Jumlah
    halaman tidak dibatasi.
    """
    if not data:
        return None

    text = extract_pdf_text(data)

    colored_rows = parse_colored_statement_pdf(data, text=text)
    if colored_rows:
        log.info("mutation_pdf_parsed", rows=len(colored_rows), via="color")
        return MutationExtraction(
            account_hint=_detect_account_hint(text),
            mutations=colored_rows,
        )

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
