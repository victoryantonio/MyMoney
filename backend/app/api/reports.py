"""
Reports API routes (US-16 — data for the Android charts/dashboard).

GET /api/reports/summary — income/expense totals + per-category breakdown.
    Period via ?period=today|week|month|last-month (default: month),
    or explicit ?start=&end= (ISO datetimes) for custom ranges.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.core.report_service import get_report_summary, parse_period_arg
from app.models.user import User
from app.schemas.report import ReportSummaryResponse

router = APIRouter(prefix="/api/reports", tags=["Reports"])

_VALID_PERIODS = {"today", "week", "month", "last-month"}


@router.get("/summary", response_model=ReportSummaryResponse)
def report_summary(
    period: str = Query(default="month", description="today | week | month | last-month"),
    start: datetime | None = Query(default=None, description="Custom range start (ISO)"),
    end: datetime | None = Query(default=None, description="Custom range end (ISO, exclusive)"),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> ReportSummaryResponse:
    """Summarize income/expense per category for a period (SQL aggregation)."""
    if start is not None and end is not None:
        start_date, end_date = start, end
        if start_date >= end_date:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="'start' must be earlier than 'end'",
            )
    elif period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Use one of: {sorted(_VALID_PERIODS)}",
        )
    else:
        tz = ZoneInfo(current_user.timezone)
        start_date, end_date = parse_period_arg(period, tz)

    return get_report_summary(db, current_user.id, start_date=start_date, end_date=end_date)
