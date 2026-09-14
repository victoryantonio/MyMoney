"""
Per-user merchant → category/account memory.

Learns from /edit and app updates. Applied after LLM parse, before write.
Never creates categories. Mapping is per user — user A does not leak to B.
"""

from __future__ import annotations

import re
import unicodedata
import uuid
from datetime import UTC, datetime

import structlog
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.account import Account
from app.models.category import Category, category_visible_clause
from app.models.merchant_alias import MerchantAlias

log = structlog.get_logger()

_SPACE_RE = re.compile(r"\s+")
_PUNCT_RE = re.compile(r"[^\w\s]+", re.UNICODE)


def normalize_merchant_key(name: str | None) -> str | None:
    if not name:
        return None
    text = unicodedata.normalize("NFKC", name).strip().lower()
    text = _PUNCT_RE.sub(" ", text)
    text = _SPACE_RE.sub(" ", text).strip()
    return text or None


def resolve_merchant_alias(
    db: Session,
    user_id: uuid.UUID,
    merchant: str | None,
) -> MerchantAlias | None:
    key = normalize_merchant_key(merchant)
    if not key:
        return None

    alias = db.scalar(
        select(MerchantAlias).where(
            MerchantAlias.user_id == user_id,
            MerchantAlias.merchant_key == key,
        )
    )
    if alias is None:
        return None

    category = db.scalar(
        select(Category).where(
            Category.id == alias.category_id,
            category_visible_clause(user_id),
        )
    )
    if category is None:
        log.info(
            "merchant_alias_stale_category",
            user_id=str(user_id),
            merchant_key=key,
        )
        return None

    if alias.account_id is not None:
        account = db.scalar(
            select(Account).where(
                Account.id == alias.account_id,
                Account.user_id == user_id,
                Account.is_active.is_(True),
            )
        )
        if account is None:
            alias.account_id = None

    return alias


def remember_merchant_correction(
    db: Session,
    *,
    user_id: uuid.UUID,
    merchant: str | None,
    category_id: uuid.UUID | None,
    account_id: uuid.UUID | None = None,
    commit: bool = False,
) -> MerchantAlias | None:
    key = normalize_merchant_key(merchant)
    if not key or category_id is None:
        return None

    alias = db.scalar(
        select(MerchantAlias).where(
            MerchantAlias.user_id == user_id,
            MerchantAlias.merchant_key == key,
        )
    )
    now = datetime.now(UTC)
    if alias is None:
        alias = MerchantAlias(
            id=uuid.uuid4(),
            user_id=user_id,
            merchant_key=key,
            category_id=category_id,
            account_id=account_id,
            hits=1,
            last_corrected_at=now,
        )
        db.add(alias)
        log.info("merchant_alias_created", user_id=str(user_id), merchant_key=key)
    else:
        alias.category_id = category_id
        if account_id is not None:
            alias.account_id = account_id
        alias.hits = (alias.hits or 0) + 1
        alias.last_corrected_at = now
        log.info("merchant_alias_updated", user_id=str(user_id), merchant_key=key)

    if commit:
        db.commit()
        db.refresh(alias)
    return alias
