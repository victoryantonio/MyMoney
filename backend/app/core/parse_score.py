"""
Rule-based parse confidence. LLM only extracts JSON; this module decides
whether the result is safe to persist without /confirm.

Bands:
  high   (>= HIGH_THRESHOLD)  → save immediately, keep /undo
  medium (>= MEDIUM_THRESHOLD) → pending; show summary, /confirm /cancel /edit
  low    (else)               → pending; require /confirm or /cancel
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Literal

HIGH_THRESHOLD = Decimal("0.75")
MEDIUM_THRESHOLD = Decimal("0.50")
DUMMY_ITEM_NAMES = frozenset({"produk", "product", "item", "barang"})


ParseBand = Literal["high", "medium", "low"]


@dataclass(frozen=True)
class ParseScore:
    score: Decimal
    band: ParseBand
    reasons: list[str] = field(default_factory=list)

    @property
    def needs_confirm(self) -> bool:
        return self.band != "high"


def _as_decimal(value: Any) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return None


def _item_line_total(item: Any) -> Decimal | None:
    if item is None:
        return None
    if isinstance(item, dict):
        qty = _as_decimal(item.get("qty"))
        price = _as_decimal(item.get("price"))
        line = _as_decimal(item.get("line_total"))
    else:
        qty = _as_decimal(getattr(item, "qty", None))
        price = _as_decimal(getattr(item, "price", None))
        line = _as_decimal(getattr(item, "line_total", None))
    if line is not None:
        return line
    if qty is None or price is None:
        return None
    return qty * price


def _item_name(item: Any) -> str:
    if isinstance(item, dict):
        raw = item.get("name") or ""
    else:
        raw = getattr(item, "name", "") or ""
    return str(raw).strip()


def _is_amount_only_text(raw_input: str | None) -> bool:
    if not raw_input:
        return False
    text = raw_input.strip().lower()
    if len(text) > 24:
        return False
    compact = text.replace(" ", "").replace(".", "").replace(",", "")
    stripped = (
        compact.replace("rp", "")
        .replace("ribu", "")
        .replace("rb", "")
        .replace("k", "")
        .replace("-", "")
    )
    return stripped.isdigit() and len(stripped) >= 2


def score_parse(
    *,
    merchant: str | None,
    category_name: str | None,
    category_was_fallback: bool,
    items: list[Any] | None,
    total: Decimal,
    raw_input: str | None = None,
    receipt_date: str | None = None,
    source: Literal["text", "receipt"] = "text",
) -> ParseScore:
    score = Decimal("0.70")
    reasons: list[str] = []
    rows = list(items or [])

    if rows:
        computed = Decimal("0")
        usable = 0
        dummy = False
        for item in rows:
            name = _item_name(item)
            if name.lower() in DUMMY_ITEM_NAMES:
                dummy = True
            line = _item_line_total(item)
            if line is not None:
                computed += line
                usable += 1
        if dummy:
            score -= Decimal("0.25")
            reasons.append("dummy_item")
        if usable:
            tolerance = max(Decimal("100"), (abs(total) * Decimal("0.02")))
            if abs(computed - total) <= tolerance:
                score += Decimal("0.15")
                reasons.append("items_match_total")
            else:
                score -= Decimal("0.20")
                reasons.append("items_mismatch_total")
        else:
            score -= Decimal("0.10")
            reasons.append("items_unusable")
    elif source == "receipt":
        score -= Decimal("0.20")
        reasons.append("receipt_no_items")

    if merchant and merchant.strip():
        score += Decimal("0.05")
        reasons.append("merchant_present")
    else:
        score -= Decimal("0.15")
        reasons.append("merchant_missing")

    resolved = (category_name or "").strip()
    if category_was_fallback or resolved.lower() == "other":
        score -= Decimal("0.20")
        reasons.append("category_fallback_other")

    if source == "receipt" and not (receipt_date and str(receipt_date).strip()):
        score -= Decimal("0.08")
        reasons.append("receipt_date_missing")

    if source == "text" and _is_amount_only_text(raw_input):
        score -= Decimal("0.20")
        reasons.append("ambiguous_short_text")

    if score < 0:
        score = Decimal("0")
    if score > 1:
        score = Decimal("1")
    score = score.quantize(Decimal("0.01"))

    if score >= HIGH_THRESHOLD:
        band: ParseBand = "high"
    elif score >= MEDIUM_THRESHOLD:
        band = "medium"
    else:
        band = "low"

    return ParseScore(score=score, band=band, reasons=reasons)
