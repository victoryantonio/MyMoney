"""
Unit tests untuk `app/core/parse_score.py` — penilaian kualitas hasil parse
yang dipakai jalur OCR nota (`app/api/receipts.py`) dan Matching Mutasi
(`app/api/mutations.py`).

Modul ini murni aturan di kode (tanpa LLM, tanpa DB), jadi seluruh test di
sini berjalan di suite manapun.
"""

from decimal import Decimal

import pytest

from app.core.parse_score import (
    HIGH_THRESHOLD,
    MEDIUM_THRESHOLD,
    ParseScore,
    _band_for,
    _clamp,
    _is_amount_only_text,
    score_mutation_parse,
    score_parse,
)

# ---------------------------------------------------------------------------
# Helper kecil supaya tiap test fokus pada satu sinyal.
# ---------------------------------------------------------------------------


def _item(name="Nasi Goreng", qty=1, price=25000):
    return {"name": name, "qty": qty, "price": price}


def _score(**overrides) -> ParseScore:
    """Skor jalur teks dengan kondisi "lengkap" sebagai default."""
    params = {
        "merchant": "Warteg Bu Yati",
        "category_name": "Food",
        "category_was_fallback": False,
        "items": [_item()],
        "total": Decimal("25000"),
        "raw_input": "makan siang di warteg 25000",
        "source": "text",
    }
    params.update(overrides)
    return score_parse(**params)


# ---------------------------------------------------------------------------
# Band + clamp
# ---------------------------------------------------------------------------


class TestBandAndClamp:
    def test_thresholds_are_inclusive(self):
        """Ambang batas memakai >= jadi 0.75 dan 0.50 masuk band di atasnya."""
        assert HIGH_THRESHOLD == Decimal("0.75")
        assert MEDIUM_THRESHOLD == Decimal("0.50")
        assert _band_for(Decimal("0.75")) == "high"
        assert _band_for(Decimal("0.74")) == "medium"
        assert _band_for(Decimal("0.50")) == "medium"
        assert _band_for(Decimal("0.49")) == "low"

    def test_clamp_keeps_score_in_unit_range(self):
        """Skor tidak boleh keluar 0..1 dan selalu 2 desimal."""
        assert _clamp(Decimal("-0.30")) == Decimal("0.00")
        assert _clamp(Decimal("1.20")) == Decimal("1.00")
        assert _clamp(Decimal("0.123456")) == Decimal("0.12")

    def test_needs_confirm_only_for_non_high(self):
        """Hanya band high yang boleh disimpan tanpa konfirmasi user."""
        assert ParseScore(Decimal("0.90"), "high").needs_confirm is False
        assert ParseScore(Decimal("0.60"), "medium").needs_confirm is True
        assert ParseScore(Decimal("0.20"), "low").needs_confirm is True


# ---------------------------------------------------------------------------
# Jalur teks/nota — score_parse()
# ---------------------------------------------------------------------------


class TestScoreParse:
    def test_complete_parse_is_high(self):
        """Merchant ada + item cocok dengan total → aman tanpa konfirmasi."""
        result = _score()
        assert result.score == Decimal("0.90")
        assert result.band == "high"
        assert result.needs_confirm is False
        assert "items_match_total" in result.reasons
        assert "merchant_present" in result.reasons

    def test_items_mismatch_with_total_is_penalized(self):
        """Total tidak sama dengan jumlah baris item → skor turun."""
        result = _score(items=[_item(price=10000)], total=Decimal("75000"))
        assert result.score == Decimal("0.55")
        assert result.band == "medium"
        assert "items_mismatch_total" in result.reasons

    def test_item_total_tolerance_allows_small_rounding(self):
        """Selisih kecil (pembulatan nota) tetap dianggap cocok."""
        result = _score(items=[_item(price=24900)], total=Decimal("25000"))
        assert "items_match_total" in result.reasons

    def test_dummy_item_name_is_penalized(self):
        """Item bernama generik ("Produk") menandakan OCR tidak membaca detail."""
        result = _score(items=[_item(name="Produk", price=25000)])
        assert result.score == Decimal("0.65")
        assert result.band == "medium"
        assert "dummy_item" in result.reasons

    def test_items_without_price_are_unusable(self):
        """Item tanpa qty/harga tidak menambah keyakinan apa pun."""
        result = _score(items=[{"name": "Nasi Goreng"}])
        assert result.score == Decimal("0.65")
        assert result.band == "medium"
        assert "items_unusable" in result.reasons

    def test_unknown_total_skips_match_signal(self):
        """OCR nota belum tahu nominal final → sinyal cocok-total dilewati."""
        result = _score(total=None)
        assert "items_total_unknown" in result.reasons
        assert "items_match_total" not in result.reasons
        assert "items_mismatch_total" not in result.reasons

    def test_receipt_without_items_is_penalized(self):
        """Nota tanpa satu pun item = ekstraksi gagal → butuh konfirmasi."""
        result = _score(items=[], source="receipt", receipt_date="2026-08-25")
        assert result.score == Decimal("0.55")
        assert result.band == "medium"
        assert "receipt_no_items" in result.reasons

    def test_receipt_without_date_is_penalized(self):
        """Tanggal nota hilang → transaksi bisa tercatat di tanggal salah."""
        with_date = _score(items=[], source="receipt", receipt_date="2026-08-25")
        without_date = _score(items=[], source="receipt", receipt_date=None)
        assert without_date.score < with_date.score
        assert "receipt_date_missing" in without_date.reasons

    def test_missing_merchant_is_penalized(self):
        """Tanpa merchant, transaksi sulit dikenali saat ditinjau."""
        result = _score(merchant=None)
        assert "merchant_missing" in result.reasons
        assert result.score == Decimal("0.70")

    def test_fallback_category_is_penalized(self):
        """Kategori fallback ("Other") berarti belum benar-benar diklasifikasi."""
        result = _score(category_was_fallback=True)
        assert result.score == Decimal("0.70")
        assert result.band == "medium"
        assert "category_fallback_other" in result.reasons

    def test_amount_only_text_is_ambiguous(self):
        """Input cuma nominal ("50rb") tidak menyebut apa yang dibeli."""
        result = _score(raw_input="50rb")
        assert result.score == Decimal("0.70")
        assert "ambiguous_short_text" in result.reasons

    def test_worst_case_clamps_to_zero_low(self):
        """Semua sinyal negatif → skor dijepit di 0.00, band low."""
        result = score_parse(
            merchant=None,
            category_name=None,
            category_was_fallback=True,
            items=[_item(name="Produk", price=1000)],
            total=Decimal("999999"),
            raw_input="50rb",
            source="text",
        )
        assert result.score == Decimal("0.00")
        assert result.band == "low"
        assert result.needs_confirm is True

    def test_full_receipt_without_total_is_high(self):
        """Nota lengkap (item, merchant, kategori, tanggal) → band high."""
        result = score_parse(
            merchant="Mixue",
            category_name="Food",
            category_was_fallback=False,
            items=[_item(name="Ice Cream Tofee", qty=2, price=21000)],
            total=None,
            receipt_date="2026-08-25",
            source="receipt",
        )
        assert result.score == Decimal("0.75")
        assert result.band == "high"
        assert result.needs_confirm is False


class TestAmountOnlyText:
    @pytest.mark.parametrize("raw", ["50rb", "Rp 25.000", "100k", "15000"])
    def test_amount_only_inputs_are_detected(self, raw):
        assert _is_amount_only_text(raw) is True

    @pytest.mark.parametrize(
        "raw",
        ["makan siang 25000", "bensin motor", "", None],
    )
    def test_text_with_context_is_not_amount_only(self, raw):
        assert _is_amount_only_text(raw) is False


# ---------------------------------------------------------------------------
# Jalur mutasi bank — score_mutation_parse()
# ---------------------------------------------------------------------------


class TestScoreMutationParse:
    def test_complete_row_with_fallback_category_is_medium(self):
        """Deskripsi+tanggal+jam lengkap, tapi kategori hanya fallback."""
        result = score_mutation_parse(
            description="QRIS TOKO ABC",
            date="2026-08-02",
            time="14:05",
            category_was_fallback=True,
        )
        assert result.score == Decimal("0.65")
        assert result.band == "medium"
        assert result.needs_confirm is True

    def test_missing_time_lowers_score(self):
        """Jam transaksi tidak tercetak di mutasi → keyakinan turun."""
        result = score_mutation_parse(
            description="QRIS TOKO ABC",
            date="2026-08-02",
            time=None,
            category_was_fallback=True,
        )
        assert result.score == Decimal("0.50")
        assert result.band == "medium"
        assert "mutation_time_missing" in result.reasons

    def test_missing_date_drops_to_low(self):
        """Tanggal hilang = transaksi bisa tercatat di waktu salah → low."""
        result = score_mutation_parse(
            description="QRIS TOKO ABC",
            date=None,
            time="14:05",
            category_was_fallback=True,
        )
        assert result.score == Decimal("0.35")
        assert result.band == "low"
        assert "mutation_date_missing" in result.reasons

    def test_missing_date_and_time_is_low(self):
        """Baris paling tidak lengkap tetap menghasilkan skor valid (>= 0)."""
        result = score_mutation_parse(
            description="QRIS TOKO ABC",
            date=None,
            time=None,
            category_was_fallback=True,
        )
        assert result.score == Decimal("0.20")
        assert result.band == "low"

    def test_short_description_is_not_enough(self):
        """Deskripsi terlalu pendek tidak cukup untuk mengenali transaksi."""
        result = score_mutation_parse(
            description="-",
            date="2026-08-02",
            time="14:05",
            category_was_fallback=True,
        )
        assert result.score == Decimal("0.40")
        assert result.band == "low"
        assert "description_missing" in result.reasons

    def test_no_fallback_category_can_reach_high(self):
        """Semua sinyal lengkap tanpa kategori fallback → band high."""
        result = score_mutation_parse(
            description="QRIS TOKO ABC",
            date="2026-08-02",
            time="14:05",
            category_was_fallback=False,
        )
        assert result.score == Decimal("0.85")
        assert result.band == "high"
        assert result.needs_confirm is False
