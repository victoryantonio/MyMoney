"""
Unit tests for receipt_ocr.py — parsing/validation of vision LLM output
(no network calls; tests the parser callback and date normalization).
"""

from decimal import Decimal

import pytest

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
        assert _parse_llm_json('{"type": "food", "items": [{"name": "x", "qty": 1, "price": 1}]}') is None

    def test_qty_zero_returns_none(self):
        assert _parse_llm_json('{"type": "expense", "items": [{"name": "x", "qty": 0, "price": 1}]}') is None

    def test_dd_mm_yyyy_date_normalized(self):
        parsed = _parse_llm_json(
            '{"type": "expense", "date": "25-08-2026", "items": [{"name": "x", "qty": 1, "price": 1}]}'
        )
        assert parsed is not None
        assert parsed.date == "2026-08-25"


class TestNormalizeDate:
    def test_dd_mm_yyyy_dash(self):
        assert _normalize_date("25-08-2026") == "2026-08-25"

    def test_dd_mm_yyyy_slash(self):
        assert _normalize_date("25/08/2026") == "2026-08-25"

    def test_iso_already(self):
        assert _normalize_date("2026-08-25") == "2026-08-25"

    def test_unparseable_returns_none(self):
        assert _normalize_date("not-a-date") is None
