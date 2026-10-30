"""
Tests untuk fitur "Matching Mutasi" (Req 9) — `app/core/mutation_matcher.py`.

Bagian pertama: unit test murni (tanpa DB, tanpa LLM) untuk normalisasi nilai
hasil ekstraksi LLM. Bagian kedua: integrasi terhadap PostgreSQL nyata untuk
`find_matches`, `resolve_upload_account`, dan `fallback_category_id`.

Panggilan LLM TIDAK diuji di sini (biaya + non-deterministik); yang diuji
adalah parser output LLM, yaitu batas kepercayaan antara output model dan
domain aplikasi.
"""

import uuid
from datetime import UTC, date, datetime
from decimal import Decimal
from pathlib import Path
from zoneinfo import ZoneInfo

import pytest

from app.core.mutation_matcher import (
    MutationExtraction,
    ParsedMutation,
    _color_direction,
    _detect_account_hint,
    _normalize_date,
    _normalize_direction,
    _normalize_time,
    _parse_llm_json,
    _PdfSpan,
    _to_decimal,
    detect_statement_period,
    extract_pdf_text,
    fallback_category_id,
    find_matches,
    is_pdf_upload,
    mutation_local_datetime,
    parse_colored_statement_pdf,
    parse_mutation_pdf,
    parse_statement_text,
    period_bounds_utc,
    render_pdf_pages,
    resolve_upload_account,
)
from app.models.account import Account
from app.models.category import Category
from app.models.pending_transaction import PendingTransaction
from app.models.transaction import Transaction


def mutation(description="QRIS MIXUE", amount="21000", direction="debit", date="2026-08-05"):
    return ParsedMutation(
        date=date,
        time=None,
        description=description,
        amount=Decimal(amount),
        direction=direction,
    )


# ── Unit: normalisasi nilai dari LLM ─────────────────────────────────────────


class TestToDecimal:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("35000", Decimal("35000")),
            ("21.000", Decimal("21000")),  # titik = ribuan (id)
            ("1.250.000", Decimal("1250000")),
            ("1,250,000.00", Decimal("1250000.00")),  # koma = ribuan (en)
            ("1.250.000,50", Decimal("1250000.50")),  # koma = desimal (id)
            ("21,5", Decimal("21.5")),
            ("1.25", Decimal("1.25")),
            ("1.250", Decimal("1250")),
            ("21,000", Decimal("21000")),
            ("Rp 1.250.000", Decimal("1250000")),
            ("-500", Decimal("-500")),
            (21000, Decimal("21000")),
            (21000.5, Decimal("21000.5")),
            (Decimal("7.5"), Decimal("7.5")),
        ],
    )
    def test_parses_formats(self, raw, expected):
        assert _to_decimal(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "   ", "saldo", True, False])
    def test_rejects_non_numbers(self, raw):
        assert _to_decimal(raw) is None


class TestNormalizeDirection:
    @pytest.mark.parametrize("raw", ["debit", "DB", "debet", "OUT", "keluar", "expense", "-"])
    def test_outgoing(self, raw):
        assert _normalize_direction(raw, None) == "debit"

    @pytest.mark.parametrize("raw", ["credit", "CR", "kredit", "in", "masuk", "income", "+"])
    def test_incoming(self, raw):
        assert _normalize_direction(raw, None) == "credit"

    def test_falls_back_to_sign(self):
        assert _normalize_direction(None, -500) == "debit"
        assert _normalize_direction(None, "-500") == "debit"

    def test_unknown_is_none(self):
        assert _normalize_direction("gift", 500) is None


class TestNormalizeDate:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [
            ("2026-08-05", "2026-08-05"),
            ("05-08-2026", "2026-08-05"),
            ("5/8/2026", "2026-08-05"),
            ("05/08/26", "2026-08-05"),
            ("2026-08-05T10:00:00", "2026-08-05"),
        ],
    )
    def test_parses(self, raw, expected):
        assert _normalize_date(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "kemarin", "31-02-2026", "13/13/2026"])
    def test_rejects(self, raw):
        assert _normalize_date(raw) is None


class TestNormalizeTime:
    @pytest.mark.parametrize(
        ("raw", "expected"),
        [("14:05", "14:05"), ("9:30", "09:30"), ("09.45", "09:45"), ("23:59", "23:59")],
    )
    def test_parses(self, raw, expected):
        assert _normalize_time(raw) == expected

    @pytest.mark.parametrize("raw", [None, "", "sore", "25:00", "10:75"])
    def test_rejects(self, raw):
        assert _normalize_time(raw) is None


class TestParseLlmJson:
    def test_plain_json(self):
        result = _parse_llm_json(
            '{"account_hint": "BCA", "mutations": ['
            '{"date": "2026-08-05", "time": "14:05", "description": "QRIS MIXUE",'
            ' "amount": 21000, "direction": "debit"}]}'
        )
        assert isinstance(result, MutationExtraction)
        assert result.account_hint == "BCA"
        assert result.mutations[0].amount == Decimal("21000")
        assert result.mutations[0].date == "2026-08-05"

    def test_strips_markdown_fence_and_prose(self):
        result = _parse_llm_json(
            "Berikut hasilnya:\n```json\n"
            '{"account_hint": null, "mutations": ['
            '{"date": null, "description": "TRANSFER MASUK", "amount": "1.500.000",'
            ' "direction": "CR"}]}\n```\nSemoga membantu.'
        )
        assert result is not None
        assert result.mutations[0].direction == "credit"
        assert result.mutations[0].amount == Decimal("1500000")

    def test_skips_invalid_rows_keeps_valid(self):
        result = _parse_llm_json(
            '{"mutations": ['
            '{"description": "SALDO AKHIR", "amount": 0, "direction": "debit"},'
            '{"description": "", "amount": 1000, "direction": "debit"},'
            '{"description": "NONTUNai", "amount": 5000, "direction": "??"},'
            '{"description": "KOPI", "amount": 18000, "direction": "db"}]}'
        )
        assert result is not None
        assert len(result.mutations) == 1
        assert result.mutations[0].description == "KOPI"

    @pytest.mark.parametrize(
        "content",
        ["", "   ", "tidak ada mutasi", "{broken json", "[]", '{"mutations": []}'],
    )
    def test_returns_none_when_unusable(self, content):
        assert _parse_llm_json(content) is None


# ── PDF e-statement (tanpa DB, LLM di-mock) ───────────────────────────────────

# Baris contoh yang lebih panjang dari MIN_PDF_TEXT_CHARS.
_STATEMENT_LINE = "05/08 TRANSFER KE 1234 BCA 21.000,00 DEBIT SALDO 1.500.000,00"


def _make_pdf(lines: list[str], pages: int = 1) -> bytes:
    """PDF mini dengan layer teks nyata (dibuat pakai PyMuPDF)."""
    import fitz

    doc = fitz.open()
    for index in range(pages):
        page = doc.new_page()
        text = lines[index] if index < len(lines) else ""
        if text:
            page.insert_text((72, 100), text)
    data = doc.tobytes()
    doc.close()
    return data


def _make_blank_pdf(pages: int = 1) -> bytes:
    """PDF tanpa layer teks — meniru hasil scan."""
    return _make_pdf([""] * pages, pages=pages)


class TestPdfDetection:
    @pytest.mark.parametrize(
        ("data", "mime", "filename", "expected"),
        [
            (b"%PDF-1.4 ...", None, None, True),
            (b"garbage", "application/pdf", "mutasi", True),
            (b"garbage", "application/pdf; charset=binary", None, True),
            (b"garbage", None, "MUTASI.PDF", True),
            (b"\x89PNG\r\n", "image/png", "mutasi.png", False),
            (b"a,b,c", "text/csv", "mutasi.csv", False),
            (b"PK\x03\x04", "application/octet-stream", "mutasi.docx", False),
            (b"", None, None, False),
        ],
    )
    def test_is_pdf_upload(self, data, mime, filename, expected):
        assert is_pdf_upload(data, mime_type=mime, filename=filename) is expected


class TestPdfTextExtraction:
    def test_reads_text_layer(self):
        pdf = _make_pdf([_STATEMENT_LINE])
        text = extract_pdf_text(pdf)
        assert "TRANSFER KE 1234" in text.replace("\n", " ")

    def test_blank_pdf_has_no_text(self):
        assert extract_pdf_text(_make_blank_pdf()).strip() == ""

    @pytest.mark.parametrize("data", [b"", b"bukan pdf sama sekali"])
    def test_invalid_pdf_is_safe(self, data):
        # PDF korup tidak boleh melempar exception (endpoint harus tetap jalan).
        assert extract_pdf_text(data).strip() == ""

    def test_render_pages_returns_png(self):
        pages = list(render_pdf_pages(_make_blank_pdf(pages=2)))
        assert len(pages) == 2
        for png in pages:
            assert png[:8] == b"\x89PNG\r\n\x1a\n"

    def test_render_has_no_page_cap(self):
        """Semua halaman di-render — tidak ada batas maksimal halaman."""
        assert len(list(render_pdf_pages(_make_blank_pdf(pages=7)))) == 7

    def test_render_invalid_pdf_is_safe(self):
        assert list(render_pdf_pages(b"bukan pdf")) == []


class TestParseMutationPdf:
    async def test_digital_pdf_uses_text_path(self, monkeypatch):
        """PDF dengan layer teks → jalur teks; vision tidak dipanggil."""
        expected = MutationExtraction(account_hint="BCA", mutations=[mutation()])

        async def fake_text(text: str):
            assert "TRANSFER KE 1234" in text.replace("\n", " ")
            return expected

        async def boom(*args, **kwargs):  # pragma: no cover - harus tidak dipanggil
            raise AssertionError("vision LLM tidak boleh dipanggil untuk PDF digital")

        monkeypatch.setattr("app.core.mutation_matcher.parse_mutation_text", fake_text)
        monkeypatch.setattr("app.core.mutation_matcher.parse_mutation_image", boom)

        result = await parse_mutation_pdf(_make_pdf([_STATEMENT_LINE]))
        assert result is expected

    async def test_scanned_pdf_reads_every_page(self, monkeypatch):
        """PDF hasil scan dibaca seluruhnya, berapa pun jumlah halamannya."""
        calls: list[str] = []

        async def fake_image(image_bytes: bytes, mime_type: str):
            assert mime_type == "image/png"
            assert image_bytes[:8] == b"\x89PNG\r\n\x1a\n"
            calls.append(mime_type)
            page = len(calls)
            return MutationExtraction(
                account_hint="BCA" if page == 1 else None,
                mutations=[mutation(description=f"MUTASI {page}")],
            )

        monkeypatch.setattr("app.core.mutation_matcher.parse_mutation_image", fake_image)

        result = await parse_mutation_pdf(_make_blank_pdf(pages=8))
        assert result is not None
        assert len(calls) == 8
        assert result.account_hint == "BCA"
        assert [m.description for m in result.mutations] == [f"MUTASI {i}" for i in range(1, 9)]

    async def test_scanned_pdf_keeps_pages_that_succeed(self, monkeypatch):
        """Halaman yang gagal dibaca tidak membatalkan halaman lain."""
        seen = 0

        async def counting_fake(image_bytes: bytes, mime_type: str):
            nonlocal seen
            seen += 1
            if seen == 1:
                return None
            return MutationExtraction(mutations=[mutation(description="HALAMAN KEDUA")])

        monkeypatch.setattr("app.core.mutation_matcher.parse_mutation_image", counting_fake)

        result = await parse_mutation_pdf(_make_blank_pdf(pages=2))
        assert seen == 2
        assert result is not None
        assert [m.description for m in result.mutations] == ["HALAMAN KEDUA"]

    async def test_returns_none_when_nothing_usable(self, monkeypatch):
        assert await parse_mutation_pdf(b"") is None

        async def fake_image(image_bytes: bytes, mime_type: str):
            return None

        monkeypatch.setattr("app.core.mutation_matcher.parse_mutation_image", fake_image)
        assert await parse_mutation_pdf(_make_blank_pdf(pages=2)) is None


# ── Integrasi: find_matches / resolve_upload_account ─────────────────────────


def _seed(db, profile, *, tx_date=datetime(2026, 8, 5, 10, 0, tzinfo=UTC)):
    """Akun + kategori + 3 transaksi; return dict agar test mudah dibaca."""
    expense_cat = Category(id=uuid.uuid4(), name="Food", type="expense", user_id=profile.id)
    income_cat = Category(id=uuid.uuid4(), name="Salary", type="income", user_id=profile.id)
    db.add_all([expense_cat, income_cat])

    bca = Account(
        id=uuid.uuid4(),
        user_id=profile.id,
        account_name="BCA Tahunan",
        initial_balance=Decimal("0"),
    )
    cash = Account(
        id=uuid.uuid4(), user_id=profile.id, account_name="Cash", initial_balance=Decimal("0")
    )
    db.add_all([bca, cash])
    db.flush()

    def tx(type_, amount, account, when, to_account=None, merchant=None):
        row = Transaction(
            id=uuid.uuid4(),
            user_id=profile.id,
            type=type_,
            total_amount=Decimal(amount),
            category_id=(
                None
                if type_ == "transfer"
                else (expense_cat.id if type_ == "expense" else income_cat.id)
            ),
            account_id=account.id,
            to_account_id=to_account.id if to_account else None,
            merchant=merchant,
            source="app",
            transaction_date=when,
        )
        db.add(row)
        return row

    expense = tx("expense", "21000", bca, tx_date, merchant="Mixue")
    income = tx("income", "1500000", bca, tx_date)
    other = tx("expense", "21000", cash, tx_date, merchant="Mixue cash")
    transfer = tx("transfer", "500000", bca, tx_date, to_account=cash)
    db.commit()
    return {
        "bca": bca,
        "cash": cash,
        "expense": expense,
        "income": income,
        "other": other,
        "transfer": transfer,
    }


class TestFindMatches:
    def test_exact_expense_match(self, db, profile):
        seeded = _seed(db, profile)
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="21000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert len(matches) == 1
        assert matches[0].transaction_id == str(seeded["expense"].id)
        assert matches[0].day_diff == 0
        assert matches[0].amount_diff == "0.00"
        assert unmatched == []

    def test_amount_within_tolerance(self, db, profile):
        seeded = _seed(db, profile)
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="21000.75", direction="debit")],
            account_id=seeded["bca"].id,
            amount_tolerance=Decimal("1.00"),
        )
        assert [m.transaction_id for m in matches] == [str(seeded["expense"].id)]
        assert unmatched == []

    def test_amount_outside_tolerance_is_unmatched(self, db, profile):
        seeded = _seed(db, profile)
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="24000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert matches == []
        assert len(unmatched) == 1

    def test_date_window_boundaries(self, db, profile):
        seeded = _seed(db, profile)
        # 2026-08-08 = 3 hari dari 2026-08-05 → masih dalam window.
        matches, _, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(date="2026-08-08")],
            account_id=seeded["bca"].id,
            date_window_days=3,
        )
        assert [m.transaction_id for m in matches] == [str(seeded["expense"].id)]
        assert matches[0].day_diff == 3

        # 2026-08-09 = 4 hari → di luar window.
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(date="2026-08-09")],
            account_id=seeded["bca"].id,
            date_window_days=3,
        )
        assert matches == []
        assert len(unmatched) == 1

    def test_credit_matches_income_not_expense(self, db, profile):
        seeded = _seed(db, profile)
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(description="GAJI", amount="1500000", direction="credit")],
            account_id=seeded["bca"].id,
        )
        assert [m.transaction_type for m in matches] == ["income"]
        assert unmatched == []

        # Nominal sama tapi arah salah (debit mencari expense) → tak cocok.
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(description="GAJI", amount="1500000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert matches == []
        assert len(unmatched) == 1

    def test_account_filter_excludes_other_accounts(self, db, profile):
        seeded = _seed(db, profile)
        matches, _, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="21000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert [m.transaction_id for m in matches] == [str(seeded["expense"].id)]
        assert seeded["other"].id not in {uuid.UUID(m.transaction_id) for m in matches}

    def test_transfer_out_and_in_respect_selected_account(self, db, profile):
        seeded = _seed(db, profile)
        # Transfer keluar dari BCA → kandidat untuk debit.
        matches, _, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="500000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert [m.transaction_type for m in matches] == ["transfer"]

        # Transfer masuk ke Cash → kandidat untuk credit pada akun Cash.
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="500000", direction="credit")],
            account_id=seeded["cash"].id,
        )
        assert [m.transaction_type for m in matches] == ["transfer"]
        assert unmatched == []

    def test_each_transaction_used_once(self, db, profile):
        seeded = _seed(db, profile)
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[
                mutation(date="2026-08-05"),
                mutation(date="2026-08-06"),
            ],
            account_id=seeded["bca"].id,
        )
        assert len(matches) == 1
        assert len(unmatched) == 1

    def test_reports_unmatched_transactions_in_range_only(self, db, profile):
        seeded = _seed(db, profile)
        # Tambah transaksi jauh di luar rentang mutasi.
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=profile.id,
                type="expense",
                total_amount=Decimal("99000"),
                account_id=seeded["bca"].id,
                source="app",
                transaction_date=datetime(2026, 1, 1, 10, 0, tzinfo=UTC),
            )
        )
        db.commit()

        matches, _, unmatched_txs = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="21000", direction="debit")],
            account_id=seeded["bca"].id,
        )
        assert len(matches) == 1
        ids = {tx.id for tx in unmatched_txs}
        # Income & transfer pada tanggal mutasi ikut dilaporkan, yang Januari tidak.
        assert seeded["income"].id in ids
        assert all(tx.transaction_date.date() == date(2026, 8, 5) for tx in unmatched_txs)

    def test_empty_mutations_returns_empty(self, db, profile):
        _seed(db, profile)
        assert find_matches(db, user_id=profile.id, mutations=[], account_id=None) == ([], [], [])


class TestResolveUploadAccount:
    def test_explicit_account_wins(self, db, profile):
        seeded = _seed(db, profile)
        assert (
            resolve_upload_account(
                db, user_id=profile.id, account_id=seeded["cash"].id, account_hint="BCA"
            )
            == seeded["cash"].id
        )

    def test_hint_matches_account_name_case_insensitively(self, db, profile):
        seeded = _seed(db, profile)
        assert (
            resolve_upload_account(
                db,
                user_id=profile.id,
                account_id=None,
                account_hint="STATEMENT REKENING bca TAHUNAN",
            )
            == seeded["bca"].id
        )

    def test_unknown_hint_returns_none(self, db, profile):
        _seed(db, profile)
        assert (
            resolve_upload_account(db, user_id=profile.id, account_id=None, account_hint="Mandiri")
            is None
        )
        assert (
            resolve_upload_account(db, user_id=profile.id, account_id=None, account_hint=None)
            is None
        )


class TestFallbackCategory:
    def test_returns_category_of_requested_type(self, db, profile):
        _seed(db, profile)
        expense_id = fallback_category_id(db, profile.id, "expense")
        income_id = fallback_category_id(db, profile.id, "income")
        assert expense_id != income_id
        expense = db.get(Category, expense_id)
        income = db.get(Category, income_id)
        assert expense.type == "expense"
        assert income.type == "income"
        # Kategori default (bila ada) menang; kalau tidak, kategori milik user.
        assert expense.user_id in (None, profile.id)
        assert income.user_id in (None, profile.id)


class TestDetectStatementPeriod:
    """Periode berkas mutasi = dasar filter transaksi (bukan seluruh riwayat)."""

    def test_single_month(self):
        period = detect_statement_period(
            [
                mutation(date="2026-09-01"),
                mutation(date="2026-09-18"),
                mutation(date="2026-09-30"),
            ]
        )
        assert period is not None
        assert period.months == ["2026-09"]
        assert period.start_date == "2026-09-01"
        assert period.end_date == "2026-09-30"
        assert period.label == "September 2026"
        assert period.first_mutation_date == "2026-09-01"
        assert period.last_mutation_date == "2026-09-30"

    def test_multi_month_span(self):
        period = detect_statement_period([mutation(date="2026-08-28"), mutation(date="2026-09-03")])
        assert period is not None
        assert period.months == ["2026-08", "2026-09"]
        assert period.start_date == "2026-08-01"
        assert period.end_date == "2026-09-30"
        assert period.label == "Agustus – September 2026"

    def test_stays_within_one_month_for_partial_dates(self):
        # 1 Feb 2026 (bukan kabisat) → akhir bulan tetap 28.
        period = detect_statement_period([mutation(date="2026-02-10")])
        assert period is not None
        assert period.end_date == "2026-02-28"

    def test_no_dates_returns_none(self):
        assert detect_statement_period([mutation(date=None)]) is None
        assert detect_statement_period([]) is None

    def test_absurdly_wide_span_is_rejected(self):
        # > 12 bulan → bukan e-statement satu periode; jangan filter ketat.
        assert (
            detect_statement_period([mutation(date="2024-01-05"), mutation(date="2026-09-05")])
            is None
        )


class TestPeriodBounds:
    def test_bounds_are_local_midnight_in_utc(self):
        period = detect_statement_period([mutation(date="2026-09-15")])
        assert period is not None
        start, end = period_bounds_utc(period, ZoneInfo("Asia/Jakarta"))
        # 1 Sep 2026 00:00 WIB (UTC+7) → 31 Agu 2026 17:00 UTC
        assert start == datetime(2026, 8, 31, 17, 0, tzinfo=UTC)
        # batas atas eksklusif = 1 Okt 2026 00:00 WIB → 30 Sep 2026 17:00 UTC
        assert end == datetime(2026, 9, 30, 17, 0, tzinfo=UTC)

    def test_transaction_at_local_month_end_is_inside_bounds(self):
        period = detect_statement_period([mutation(date="2026-09-15")])
        assert period is not None
        start, end = period_bounds_utc(period, ZoneInfo("Asia/Jakarta"))
        # 30 Sep 2026 23:30 WIB → 16:30 UTC, masih < batas atas.
        last = datetime(2026, 9, 30, 23, 30, tzinfo=ZoneInfo("Asia/Jakarta"))
        assert start <= last.astimezone(UTC) < end


class TestMutationLocalDatetime:
    def test_keeps_mutation_time(self):
        row = ParsedMutation(
            date="2026-09-15",
            time="13:21",
            description="QRIS",
            amount=Decimal("21000"),
            direction="debit",
        )
        local = mutation_local_datetime(row, ZoneInfo("Asia/Jakarta"))
        assert local is not None
        assert local.isoformat() == "2026-09-15T13:21:00+07:00"
        assert local.astimezone(UTC) == datetime(2026, 9, 15, 6, 21, tzinfo=UTC)

    def test_missing_time_defaults_to_midnight(self):
        local = mutation_local_datetime(mutation(), ZoneInfo("Asia/Jakarta"))
        assert local is not None
        assert local.hour == 0
        assert local.minute == 0

    def test_invalid_time_defaults_to_midnight(self):
        row = ParsedMutation(
            date="2026-09-15",
            time="jam sebelas",
            description="QRIS",
            amount=Decimal("21000"),
            direction="debit",
        )
        local = mutation_local_datetime(row, ZoneInfo("Asia/Jakarta"))
        assert local is not None
        assert (local.hour, local.minute) == (0, 0)

    def test_no_date_returns_none(self):
        assert mutation_local_datetime(mutation(date=None), ZoneInfo("Asia/Jakarta")) is None


class TestFindMatchesPeriodFilter:
    """Filter berbasis bulan berkas, bukan min/max tanggal mutasi."""

    def test_excludes_transactions_outside_detected_month(self, db, profile):
        seeded = _seed(db, profile, tx_date=datetime(2026, 8, 5, 10, 0, tzinfo=UTC))
        # Mutasi September 2026: transaksi Agustus tidak boleh jadi kandidat.
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(date="2026-09-05")],
            account_id=seeded["bca"].id,
            date_window_days=90,
        )
        assert matches == []
        assert len(unmatched) == 1

    def test_includes_transaction_in_same_month_far_apart(self, db, profile):
        seeded = _seed(db, profile, tx_date=datetime(2026, 9, 2, 10, 0, tzinfo=UTC))
        matches, unmatched, _ = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(date="2026-09-28")],
            account_id=seeded["bca"].id,
            date_window_days=30,
        )
        assert [m.transaction_id for m in matches] == [str(seeded["expense"].id)]
        assert unmatched == []

    def test_unmatched_transactions_limited_to_month(self, db, profile):
        seeded = _seed(db, profile, tx_date=datetime(2026, 9, 10, 10, 0, tzinfo=UTC))
        db.add(
            Transaction(
                id=uuid.uuid4(),
                user_id=profile.id,
                type="expense",
                total_amount=Decimal("77000"),
                account_id=seeded["bca"].id,
                source="app",
                transaction_date=datetime(2026, 7, 1, 10, 0, tzinfo=UTC),
            )
        )
        db.commit()

        _, _, unmatched_txs = find_matches(
            db,
            user_id=profile.id,
            mutations=[mutation(amount="21000", direction="debit", date="2026-09-10")],
            account_id=seeded["bca"].id,
        )
        assert all(tx.transaction_date.year == 2026 for tx in unmatched_txs)
        assert all(tx.transaction_date.month == 9 for tx in unmatched_txs)


class TestCreatePendingsTimestamp:
    """`_create_pendings` menyimpan tanggal+jam ASLI dari mutasi."""

    def test_pending_gets_mutation_datetime_and_timezone(self, db, profile):
        from app.api.mutations import _create_pendings

        seeded = _seed(db, profile)
        row = ParsedMutation(
            date="2026-09-14",
            time="13:21",
            description="QRIS KOPI KENANGAN",
            amount=Decimal("777777"),
            direction="debit",
        )
        ids = _create_pendings(
            db,
            current_user=profile,
            mutations=[row],
            account_id=seeded["bca"].id,
            source_label="SeaBank",
            tz=ZoneInfo("Asia/Jakarta"),
        )
        assert len(ids) == 1

        pending = db.get(PendingTransaction, ids[0])
        assert pending is not None
        # 14 Sep 2026 13:21 WIB → 06:21 UTC
        assert pending.transaction_date == datetime(2026, 9, 14, 6, 21, tzinfo=UTC)
        assert pending.timezone == "Asia/Jakarta"

    def test_missing_time_uses_local_midnight(self, db, profile):
        from app.api.mutations import _create_pendings

        seeded = _seed(db, profile)
        ids = _create_pendings(
            db,
            current_user=profile,
            mutations=[mutation(date="2026-09-14")],
            account_id=seeded["bca"].id,
            source_label="SeaBank",
            tz=ZoneInfo("Asia/Jakarta"),
        )
        pending = db.get(PendingTransaction, ids[0])
        assert pending is not None
        # 14 Sep 2026 00:00 WIB → 13 Sep 2026 17:00 UTC
        assert pending.transaction_date == datetime(2026, 9, 13, 17, 0, tzinfo=UTC)


# ── Parser deterministik (tanpa LLM) ─────────────────────────────────────────

FIXTURES_DIR = Path(__file__).parent / "fixtures"
SEABANK_FIXTURE = FIXTURES_DIR / "seabank_2026_09.txt"
SEABANK_LAYOUT_FIXTURE = FIXTURES_DIR / "seabank_2026_09_layout.txt"
BCA_LAYOUT_FIXTURE = FIXTURES_DIR / "bca_2026_09_layout.txt"


def _seabank_rows():
    return parse_statement_text(SEABANK_FIXTURE.read_text(encoding="utf-8"))


class TestStatementTextParser:
    """Regresi format e-statement SeaBank (kolom Keluar/Masuk + saldo berjalan)."""

    def test_reads_every_row(self):
        rows = _seabank_rows()
        assert len(rows) == 71
        # Baris ringkasan tidak boleh ikut terbaca.
        assert not any(row.description.startswith("Saldo") for row in rows)
        assert not any("Periode" in row.description for row in rows)

    def test_debit_and_credit_columns_are_mapped(self):
        rows = _seabank_rows()

        def first(description: str):
            return next(row for row in rows if row.description == description)

        debit = first('Pembayaran NASI PINDANG KUDUS "BU')
        assert debit.direction == "debit"
        assert debit.amount == Decimal("18000")

        sweep = first("Transfer DANA")
        assert sweep.direction == "credit"
        assert sweep.amount == Decimal("450000")

        big_in = first("PERMATA 900000000004 NASABAH CONTOH")
        assert big_in.direction == "credit"
        assert big_in.amount == Decimal("2101922")

        big_out = first("Transfer REKAN.A SeaBank 900000000003")
        assert big_out.direction == "debit"
        assert big_out.amount == Decimal("750000")

    def test_year_inferred_for_month_name_dates(self):
        rows = _seabank_rows()
        assert rows[0].date == "2026-09-01"
        assert rows[-1].date == "2026-09-30"

    def test_totals_match_statement_summary(self):
        rows = _seabank_rows()
        debit = sum((row.amount for row in rows if row.direction == "debit"), Decimal("0"))
        credit = sum((row.amount for row in rows if row.direction == "credit"), Decimal("0"))
        assert debit == Decimal("3288616")
        assert credit == Decimal("2553554")

    def test_balance_column_is_never_used_as_amount(self):
        # Layout asli: saldo berjalan (1.744.505, 1.726.505, 1.009.324, ...)
        # tidak boleh terbaca sebagai nominal transaksi.
        rows = parse_statement_text(SEABANK_LAYOUT_FIXTURE.read_text(encoding="utf-8"))
        balances = {
            Decimal("1744505"),
            Decimal("1726505"),
            Decimal("1744386"),
            Decimal("1009324"),
        }
        assert all(row.amount not in balances for row in rows)

    def test_interest_rows_are_kept_as_income(self):
        interest = [row for row in _seabank_rows() if row.description == "Bunga Tabungan"]
        assert len(interest) == 30
        assert all(row.direction == "credit" for row in interest)

    def test_non_tabular_text_returns_no_rows(self):
        assert parse_statement_text("Halo, ini bukan mutasi bank.") == []

    def test_row_with_both_columns_filled_is_skipped(self):
        header = f"{'Tanggal':<10}{'Keterangan':<20}{'Keluar':>11}{'Masuk':>12}"
        text = "\n".join(
            [
                header,
                f"{'01 SEP':<10}{'Transfer DANA':<20}{'18.000':>11}{'450.000':>12}",
                f"{'02 SEP':<10}{'Bunga Tabungan':<20}{'':>11}{'119':>12}",
            ]
        )
        rows = parse_statement_text(text)
        assert [(r.description, r.direction) for r in rows] == [("Bunga Tabungan", "credit")]

    def test_csv_with_semicolon(self):
        text = (
            "Tanggal;Keterangan;Keluar;Masuk;Saldo\n"
            "01/09/2026;Transfer: DANA;;450000;1665853\n"
            "02/09/2026;Pembayaran: TOKO IIN;100000;;1215769\n"
        )
        rows = parse_statement_text(text)
        assert [(r.description, r.direction, r.amount) for r in rows] == [
            ("Transfer: DANA", "credit", Decimal("450000")),
            ("Pembayaran: TOKO IIN", "debit", Decimal("100000")),
        ]

    def test_whitespace_pdf_layout_uses_header_positions(self):
        header = (
            f"{'Tanggal':<10}{'Keterangan Transaksi':<40}{'Keluar':>15}{'Masuk':>16}{'Saldo':>18}"
        )

        def row(day: str, description: str, keluar: str = "", masuk: str = "", saldo: str = ""):
            return f"{day:<10}{description:<40}{keluar:>15}{masuk:>16}{saldo:>18}"

        text = "\n".join(
            [
                "Bank: SeaBank",
                "Periode Mutasi: 01 SEP 2026 sampai 30 SEP 2026",
                header,
                row("01 SEP", "Bunga Tabungan", masuk="119", saldo="1.744.505"),
                row("01 SEP", "Pembayaran: NASI PINDANG KUDUS", keluar="18.000", saldo="1.726.505"),
                row("07 SEP", "Transfer: DANA", masuk="450.000", saldo="1.665.853"),
                row(
                    "07 SEP",
                    "Transfer: ADE.A.PERTIWI SeaBank 901280308455",
                    keluar="750.000",
                    saldo="915.853",
                ),
            ]
        )

        rows = parse_statement_text(text)
        assert [(r.direction, r.amount) for r in rows] == [
            ("credit", Decimal("119")),
            ("debit", Decimal("18000")),
            ("credit", Decimal("450000")),
            ("debit", Decimal("750000")),
        ]
        assert [r.date for r in rows] == [
            "2026-09-01",
            "2026-09-01",
            "2026-09-07",
            "2026-09-07",
        ]

    def test_llm_split_debit_credit_columns(self):
        extraction = _parse_llm_json(
            '{"mutations": [{"date": "2026-09-01", "description": "TOKO IIN", '
            '"debit": 18000, "credit": null}]}'
        )
        assert extraction is not None
        assert extraction.mutations[0].direction == "debit"
        assert extraction.mutations[0].amount == Decimal("18000")


def _seabank_layout_lines() -> list[str]:
    """Fixture SeaBank → teks bertata letak spasi (mirip text layer PDF)."""
    lines = [
        "Informasi Rekening",
        "Bank: SeaBank",
        "Periode Mutasi: 01 SEP 2026 sampai 30 SEP 2026",
        f"{'Tanggal':<10}{'Keterangan Transaksi':<58}{'Keluar':>12}{'Masuk':>12}{'Saldo Akhir':>16}",
    ]
    for raw in SEABANK_FIXTURE.read_text(encoding="utf-8").splitlines():
        if not raw.startswith("|") or set(raw) <= set("|- "):
            continue
        cells = [cell.strip() for cell in raw.strip().strip("|").split("|")]
        if cells[0] == "Tanggal":
            continue
        date, description, keluar, masuk, saldo = cells
        lines.append(f"{date:<10}{description:<58}{keluar:>12}{masuk:>12}{saldo:>16}")
    return lines


def _make_mono_pdf(lines: list[str], per_page: int = 50) -> bytes:
    """PDF dengan font monospace supaya kolom hasil ekstraksi tetap sejajar."""
    import fitz

    doc = fitz.open()
    page = doc.new_page()
    for index, line in enumerate(lines):
        if index and index % per_page == 0:
            page = doc.new_page()
        page.insert_text(
            (40, 60 + (index % per_page) * 11),
            line,
            fontname="cour",
            fontsize=8,
        )
    data = doc.tobytes()
    doc.close()
    return data


class TestSeabankLayoutText:
    """Text layer e-statement SeaBank asli (kolom Keluar/Masuk, keterangan 2 sisi)."""

    @staticmethod
    def _text() -> str:
        return SEABANK_LAYOUT_FIXTURE.read_text(encoding="utf-8")

    def test_reads_every_row_from_text_layer(self):
        rows = parse_statement_text(self._text())
        assert len(rows) == 71
        assert not any(row.description.startswith(("Saldo", "TOTAL", "REKENING")) for row in rows)

    def test_totals_match_summary_block(self):
        rows = parse_statement_text(self._text())
        debit = sum((row.amount for row in rows if row.direction == "debit"), Decimal("0"))
        credit = sum((row.amount for row in rows if row.direction == "credit"), Decimal("0"))
        # RINGKASAN: TRANSAKSI KELUAR 3.288.616 - TRANSAKSI MASUK 2.553.554
        assert debit == Decimal("3288616")
        assert credit == Decimal("2553554")

    def test_description_joined_from_lines_around_the_date(self):
        rows = parse_statement_text(self._text())
        descriptions = [row.description for row in rows]
        assert descriptions[0] == "Bunga Tabungan"
        assert 'Pembayaran NASI PINDANG KUDUS "BU' in descriptions
        assert "Pembayaran TREETOP FITNESS" in descriptions

    def test_html_entities_are_decoded(self):
        text = self._text()
        assert "&quot;" in text  # bukti berkas asli memuat entitas HTML
        rows = parse_statement_text(text)
        assert all("&quot;" not in row.description for row in rows)
        assert any('"' in row.description for row in rows)

    def test_balance_and_summary_rows_are_ignored(self):
        rows = parse_statement_text(self._text())
        amounts = {row.amount for row in rows}
        assert Decimal("1009324") not in amounts  # SALDO AKHIR
        assert Decimal("1744386") not in amounts  # SALDO AWAL

    def test_dates_use_period_year(self):
        rows = parse_statement_text(self._text())
        assert {row.date[:7] for row in rows} == {"2026-09"}
        assert rows[0].date == "2026-09-01"
        assert rows[-1].date == "2026-09-30"

    def test_account_hint_detected_from_header(self):
        assert _detect_account_hint(self._text()) == "SeaBank"


class TestBcaLayoutText:
    """Text layer rekening koran BCA: satu kolom MUTASI + sufiks DB/CR."""

    @staticmethod
    def _text() -> str:
        return BCA_LAYOUT_FIXTURE.read_text(encoding="utf-8")

    def test_reads_every_row_from_text_layer(self):
        rows = parse_statement_text(self._text())
        assert len(rows) == 25

    def test_totals_match_summary_block(self):
        rows = parse_statement_text(self._text())
        debit = sum((row.amount for row in rows if row.direction == "debit"), Decimal("0"))
        credit = sum((row.amount for row in rows if row.direction == "credit"), Decimal("0"))
        # Blok akhir: MUTASI DB 9.100.842 - MUTASI CR 8.815.858
        assert debit == Decimal("9100842")
        assert credit == Decimal("8815858")

    def test_saldo_awal_row_is_not_a_transaction(self):
        rows = parse_statement_text(self._text())
        amount = Decimal("732783.13")
        assert all(row.amount != amount for row in rows)
        assert not any("SALDO AWAL" in row.description.upper() for row in rows)

    def test_db_suffix_means_debit(self):
        rows = parse_statement_text(self._text())
        adm = next(row for row in rows if row.description == "BIAYA ADM 0998")
        assert adm.direction == "debit"
        assert adm.amount == Decimal("10000.00")

    def test_incoming_rows_without_suffix_are_credit(self):
        rows = parse_statement_text(self._text())
        setoran = [row for row in rows if row.description.startswith("SETORAN VIA CDM")]
        assert len(setoran) == 2
        assert all(row.direction == "credit" for row in setoran)
        assert sum((row.amount for row in setoran), Decimal("0")) == Decimal("4600000.00")

    def test_date_without_year_uses_period(self):
        rows = parse_statement_text(self._text())
        assert rows[0].date == "2026-09-01"
        assert {row.date[:7] for row in rows} == {"2026-09"}

    def test_account_hint_detected_from_header(self):
        assert _detect_account_hint(self._text()) == "BCA"

    async def test_pdf_path_returns_rows_without_llm(self, monkeypatch):
        async def boom(*args, **kwargs):  # pragma: no cover - harus tidak dipanggil
            raise AssertionError("LLM tidak boleh dipanggil untuk PDF bertext-layer")

        monkeypatch.setattr("app.core.mutation_matcher.call_llm", boom)
        text = self._text()
        monkeypatch.setattr("app.core.mutation_matcher.extract_pdf_text", lambda data: text)

        result = await parse_mutation_pdf(b"%PDF-1.4 dummy")

        assert result is not None
        assert result.account_hint == "BCA"
        assert len(result.mutations) == 25


class TestSeabankPdfEndToEnd:
    """PDF e-statement SeaBank → parser deterministik, tanpa memanggil LLM."""

    async def test_full_statement_read_without_llm(self, monkeypatch):
        async def boom(*args, **kwargs):  # pragma: no cover - harus tidak dipanggil
            raise AssertionError("LLM tidak boleh dipanggil untuk PDF bertabel")

        monkeypatch.setattr("app.core.mutation_matcher.call_llm", boom)

        pdf = _make_mono_pdf(_seabank_layout_lines())
        result = await parse_mutation_pdf(pdf)

        assert result is not None
        assert result.account_hint == "SeaBank"
        assert len(result.mutations) == 71

        debit = sum(
            (row.amount for row in result.mutations if row.direction == "debit"),
            Decimal("0"),
        )
        credit = sum(
            (row.amount for row in result.mutations if row.direction == "credit"),
            Decimal("0"),
        )
        assert debit == Decimal("3288616")
        assert credit == Decimal("2553554")
        assert result.mutations[0].date == "2026-09-01"
        assert result.mutations[0].description == "Bunga Tabungan"


# ── PDF dengan arah dana dari warna teks (Permata) ───────────────────────────

PERMATA_COLOR_FIXTURE = FIXTURES_DIR / "permata_2026_09_color.txt"
PERMATA_LAYOUT_FIXTURE = FIXTURES_DIR / "permata_2026_09_layout.txt"
PERMATA_PAGE_WIDTH = 840
PERMATA_PAGE_HEIGHT = 1242


def _permata_color_spans() -> dict[int, list[tuple[int, float, float, float, str]]]:
    """Fixture span Permata → {halaman: [(warna, y, x, tinggi, teks)]}."""
    pages: dict[int, list[tuple[int, float, float, float, str]]] = {}
    for raw in PERMATA_COLOR_FIXTURE.read_text(encoding="utf-8").splitlines():
        if not raw.strip():
            continue
        page, color, y, x, height, text = raw.split("|", 5)
        pages.setdefault(int(page), []).append(
            (int(color, 16), float(y), float(x), float(height), text)
        )
    return pages


def _make_color_pdf() -> bytes:
    """Bangun PDF mirip statement Permata: arah dana hanya ditandai warna teks."""
    import fitz

    doc = fitz.open()
    for _page_number, spans in sorted(_permata_color_spans().items()):
        page = doc.new_page(width=PERMATA_PAGE_WIDTH, height=PERMATA_PAGE_HEIGHT)
        for color, y, x, height, text in spans:
            page.insert_text(
                (x, y + height * 0.8),
                text,
                fontsize=max(height * 0.8, 4.0),
                color=(
                    ((color >> 16) & 0xFF) / 255,
                    ((color >> 8) & 0xFF) / 255,
                    (color & 0xFF) / 255,
                ),
            )
    data = doc.tobytes()
    doc.close()
    return data


class TestColorDirection:
    """Warna teks → arah dana (Permata: hijau masuk, merah keluar)."""

    @pytest.mark.parametrize(
        ("color", "expected"),
        [
            (0xDD0C25, "debit"),
            (0x8873, "credit"),
            (0x008873, "credit"),
            (0x000000, None),
            (0xFFFFFF, None),
            (0x444444, None),
        ],
    )
    def test_color_maps_to_direction(self, color, expected):
        assert _color_direction(color) == expected


class TestPermataColorPdf:
    """E-statement Permata: nominal hijau/merah, tanpa kolom Keluar/Masuk."""

    @staticmethod
    def _rows():
        return parse_colored_statement_pdf(_make_color_pdf())

    def test_reads_every_transaction(self):
        assert len(self._rows()) == 15

    def test_red_amounts_are_debit_and_green_are_credit(self):
        rows = self._rows()
        direction = {(row.amount, row.direction) for row in rows}
        assert (Decimal("2000.00"), "debit") in direction  # Rp 2,000.00 merah
        assert (Decimal("7006406.00"), "credit") in direction  # Rp 7,006,406 hijau

    def test_totals_match_statement(self):
        rows = self._rows()
        debit = sum((row.amount for row in rows if row.direction == "debit"), Decimal("0"))
        credit = sum((row.amount for row in rows if row.direction == "credit"), Decimal("0"))
        assert debit == Decimal("7924015.00")
        assert credit == Decimal("8209830.00")

    def test_dates_carried_across_pages(self):
        rows = self._rows()
        assert [row.date for row in rows] == [
            "2026-09-30",
            "2026-09-27",
            "2026-09-25",
            "2026-09-25",
            "2026-09-25",
            "2026-09-22",
            "2026-09-16",
            "2026-09-15",
            "2026-09-15",
            "2026-09-15",
            "2026-09-13",
            "2026-09-13",
            "2026-09-08",
            "2026-09-07",
            "2026-09-01",
        ]

    def test_description_follows_the_amount_line(self):
        rows = self._rows()
        assert rows[0].description == "Biaya Adm Bulanan Kartu 9999999999999999 September 2026"
        assert rows[0].direction == "debit"
        assert rows[1].description == "QR PAYMENT 13:21:49 HPM PARAGON CITY SEMARANG"
        assert rows[-1].description == "PB Bagi Hasil"
        assert rows[-1].amount == Decimal("79.00")
        assert rows[-1].direction == "credit"

    def test_account_hint_is_permata_not_the_transfer_counterparty(self):
        # Keterangan memuat "PT BANK SEABANK INDONESIA" satu kali, sedangkan
        # nama bank penerbit muncul jauh lebih sering.
        text = PERMATA_LAYOUT_FIXTURE.read_text(encoding="utf-8")
        assert _detect_account_hint(text) == "Permata"

    async def test_pdf_path_uses_color_and_never_calls_llm(self, monkeypatch):
        async def boom(*args, **kwargs):  # pragma: no cover - harus tidak dipanggil
            raise AssertionError("LLM tidak boleh dipanggil untuk PDF berwarna")

        monkeypatch.setattr("app.core.mutation_matcher.call_llm", boom)

        result = await parse_mutation_pdf(_make_color_pdf())

        assert result is not None
        assert result.account_hint == "Permata"
        assert len(result.mutations) == 15
        debit = sum(
            (row.amount for row in result.mutations if row.direction == "debit"),
            Decimal("0"),
        )
        assert debit == Decimal("7924015.00")

    def test_uncolored_amount_skips_color_path(self, monkeypatch):
        # PDF bertabel biasa (nominal hitam) tidak boleh dibaca jalur warna:
        # arah dana tidak tercetak, jadi tidak boleh ditebak.
        monkeypatch.setattr(
            "app.core.mutation_matcher._page_spans",
            lambda page: [
                _PdfSpan(text="Rp 10.000", x=10.0, y=20.0, height=12.0, color=0x000000),
            ],
        )
        assert parse_colored_statement_pdf(b"%PDF-1.4 dummy", text="September 2026") == []
