"""
Reports API routes (US-16 — data for the Android charts/dashboard).

GET /api/reports/summary — income/expense totals + per-category breakdown.
GET /api/reports/trend    — daily income/expense series (line chart).
    Period via ?period=today|week|month|last-month (default: month),
    or explicit ?start=&end= (ISO datetimes) for custom ranges.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from app.api.deps import get_db, require_active_user
from app.core.report_service import get_report_summary, get_report_trend, parse_period_arg
from app.models.user import User
from app.schemas.report import ReportSummaryResponse, ReportTrendResponse

router = APIRouter(prefix="/api/reports", tags=["Reports"])

_VALID_PERIODS = {"today", "week", "month", "last-month"}


def _resolve_boundaries(
    period: str,
    start: datetime | None,
    end: datetime | None,
    tz: ZoneInfo,
) -> tuple[datetime, datetime]:
    """Shared period/custom-range parsing for summary & trend endpoints."""
    if start is not None and end is not None:
        if start >= end:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="'start' must be earlier than 'end'",
            )
        return start, end
    if period not in _VALID_PERIODS:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid period '{period}'. Use one of: {sorted(_VALID_PERIODS)}",
        )
    return parse_period_arg(period, tz)


@router.get("/summary", response_model=ReportSummaryResponse)
def report_summary(
    period: str = Query(default="month", description="today | week | month | last-month"),
    start: datetime | None = Query(default=None, description="Custom range start (ISO)"),
    end: datetime | None = Query(default=None, description="Custom range end (ISO, exclusive)"),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> ReportSummaryResponse:
    """Summarize income/expense per category for a period (SQL aggregation)."""
    tz = ZoneInfo(current_user.timezone)
    start_date, end_date = _resolve_boundaries(period, start, end, tz)

    return get_report_summary(db, current_user.id, start_date=start_date, end_date=end_date)


@router.get("/trend", response_model=ReportTrendResponse)
def report_trend(
    period: str = Query(default="month", description="today | week | month | last-month"),
    start: datetime | None = Query(default=None, description="Custom range start (ISO)"),
    end: datetime | None = Query(default=None, description="Custom range end (ISO, exclusive)"),
    current_user: User = Depends(require_active_user),
    db: Session = Depends(get_db),
) -> ReportTrendResponse:
    """Daily income/expense series for the period (for the cash-flow line chart)."""
    tz = ZoneInfo(current_user.timezone)
    start_date, end_date = _resolve_boundaries(period, start, end, tz)

    return get_report_trend(
        db,
        current_user.id,
        start_date=start_date,
        end_date=end_date,
        tz=tz,
    )
