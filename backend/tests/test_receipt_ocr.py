"""
Unit tests for receipt_ocr.py — parsing/validation of vision LLM output
(no network calls; tests the parser callback and date normalization).
"""

from decimal import Decimal

from app.core.receipt_ocr import _normalize_date, _parse_llm_json


class TestParseLlmJson:
    def test_valid_receipt_parses(self):
        content = """{
          "type": "expense",
          "merchant": "Mixue",
          "date": "2026-08-25",
          "items": [
            {"name": "Ice Cream Tofee Hazelnut Latte (M)", "qty": 2, "price": 21000}
          ]
        }"""
        parsed = _parse_llm_json(content)
        assert parsed is not None
        assert parsed.merchant == "Mixue"
        assert parsed.date == "2026-08-25"
        assert len(parsed.items) == 1
        assert parsed.items[0].name == "Ice Cream Tofee Hazelnut Latte (M)"
        assert parsed.items[0].qty == Decimal("2")
        assert parsed.items[0].price == Decimal("21000")

    def test_recognized_error_returns_none(self):
        assert _parse_llm_json('{"error": "unrecognized"}') is None

    def test_malformed_json_returns_none(self):
        assert _parse_llm_json("{not json") is None

    def test_no_items_returns_none(self):
        assert _parse_llm_json('{"type": "expense", "items": []}') is None

    def test_invalid_type_returns_none(self):
        assert (
            _parse_llm_json('{"type": "food", "items": [{"name": "x", "qty": 1, "price": 1}]}')
            is None
        )

    def test_qty_zero_returns_none(self):
        assert (
            _parse_llm_json('{"type": "expense", "items": [{"name": "x", "qty": 0, "price": 1}]}')
            is None
        )

    def test_dd_mm_yyyy_date_normalized(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "date": "25-08-2026", "items": [{"name": "x", "qty": 1, "price": 1}]}'
        )
        assert parsed is not None
        assert parsed.date == "2026-08-25"


class TestTolerantItemNormalization:
    """The AEON-receipt regression: clear text but strict schema rejected
    string quantities ("2x") and separator-formatted prices ("29,960")."""

    def test_string_qty_with_x(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "Mixue", "qty": "2x", "price": 21000}]}'
        )
        assert parsed is not None
        assert parsed.items[0].qty == Decimal("2")
        assert parsed.items[0].price == Decimal("21000")

    def test_string_qty_with_unit(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "Cuci", "qty": "5.3 kg", "price": 4528}]}'
        )
        assert parsed is not None
        assert parsed.items[0].qty == Decimal("5.3")

    def test_price_with_comma_separator(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "SPC EBIKTSU R", "qty": 1, "price": "29,960"}]}'
        )
        assert parsed is not None
        assert parsed.items[0].price == Decimal("29960")

    def test_price_with_dot_separator(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "Snack", "qty": 1, "price": "Rp21.000"}]}'
        )
        assert parsed is not None
        assert parsed.items[0].price == Decimal("21000")

    def test_line_total_only_derives_price(self):
        """A single-total line (no qty/price) → qty 1, price = line_total."""
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "M STR CHOCO", "line_total": "6,750"}]}'
        )
        assert parsed is not None
        assert parsed.items[0].qty == Decimal("1")
        assert parsed.items[0].price == Decimal("6750")
        assert parsed.items[0].line_total == Decimal("6750")

    def test_price_derived_from_qty_and_line_total(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "items": [{"name": "Laundry", "qty": 5.3, "line_total": 24000}]}'
        )
        assert parsed is not None
        assert parsed.items[0].price == Decimal("4528")  # 24000 / 5.3 rounded

    def test_discount_row_dropped_valid_rows_kept(self):
        """Negative-price discount rows (RTC -12.840) are dropped, others kept."""
        parsed = _parse_llm_json(
            '{"type": "expense", "items": ['
            '{"name": "SPC EBIKTSU R", "qty": 1, "price": "29,960"},'
            '{"name": "RTC", "price": "-12.840"},'
            '{"name": "M STR CHOCO", "qty": 1, "price": "6,750"}'
            "]}"
        )
        assert parsed is not None
        assert len(parsed.items) == 2
        assert parsed.items[0].name == "SPC EBIKTSU R"
        assert parsed.items[1].name == "M STR CHOCO"

    def test_one_invalid_row_does_not_kill_parse(self):
        """One row with qty 0 must not fail the whole receipt."""
        parsed = _parse_llm_json(
            '{"type": "expense", "items": ['
            '{"name": "x", "qty": 0, "price": 1},'
            '{"name": "y", "qty": 1, "price": 2}'
            "]}"
        )
        assert parsed is not None
        assert len(parsed.items) == 1
        assert parsed.items[0].name == "y"


class TestNormalizeDate:
    def test_dd_mm_yyyy_dash(self):
        assert _normalize_date("25-08-2026") == "2026-08-25"

    def test_dd_mm_yyyy_slash(self):
        assert _normalize_date("25/08/2026") == "2026-08-25"

    def test_iso_already(self):
        assert _normalize_date("2026-08-25") == "2026-08-25"

    def test_unparseable_returns_none(self):
        assert _normalize_date("not-a-date") is None
