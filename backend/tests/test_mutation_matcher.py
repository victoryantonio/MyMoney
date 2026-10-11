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

import pytest

from app.core.mutation_matcher import (
    MutationExtraction,
    ParsedMutation,
    _normalize_date,
    _normalize_direction,
    _normalize_time,
    _parse_llm_json,
    _to_decimal,
    fallback_category_id,
    find_matches,
    resolve_upload_account,
)
from app.models.account import Account
from app.models.category import Category
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
            category_id=None
            if type_ == "transfer"
            else (expense_cat.id if type_ == "expense" else income_cat.id),
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
