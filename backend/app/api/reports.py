"""
reports.py — REST endpoints for report data consumed by Android app.
"""
from datetime import datetime, timezone, timedelta

import uuid
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import current_user_dep
from app.core import report_service
from app.db.session import get_db
from app.models.models import User

router = APIRouter(prefix="/reports", tags=["Reports"])


@router.get("/summary")
async def get_summary(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """
    Return income/expense summary with per-category breakdown.
    Defaults to current month if no dates provided.
    """
    now = datetime.now(timezone.utc)
    if not date_from:
        date_from = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
    if not date_to:
        date_to = now

    return await report_service.get_summary(db, current_user.id, date_from, date_to)


@router.get("/trend")
async def get_daily_trend(
    date_from: datetime | None = Query(default=None),
    date_to: datetime | None = Query(default=None),
    current_user: User = Depends(current_user_dep),
    db: AsyncSession = Depends(get_db),
) -> list:
    """Return daily income/expense trend for chart rendering."""
    now = datetime.now(timezone.utc)
    if not date_from:
        date_from = now - timedelta(days=30)
    if not date_to:
        date_to = now

    return await report_service.get_daily_trend(db, current_user.id, date_from, date_to)
