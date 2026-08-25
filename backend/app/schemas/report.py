"""
Pydantic schemas for reports (US-11, US-16, US-17).
"""

from datetime import date, datetime
from decimal import Decimal

from pydantic import BaseModel, Field


class CategoryTotal(BaseModel):
    """One row of the per-category breakdown (name + type + summed amount)."""

    name: str
    type: str  # 'income' | 'expense'
    total: Decimal = Field(default_factory=Decimal)


class ReportSummaryResponse(BaseModel):
    """Period summary: overall totals plus a per-category breakdown."""

    start_date: datetime
    end_date: datetime  # exclusive upper bound
    total_income: Decimal = Field(default_factory=Decimal)
    total_expense: Decimal = Field(default_factory=Decimal)
    net: Decimal = Field(default_factory=Decimal)
    categories: list[CategoryTotal] = Field(default_factory=list)


class TrendPoint(BaseModel):
    """One day of the cash-flow trend: date + income & expense totals."""

    date: date
    income: Decimal = Field(default_factory=Decimal)
    expense: Decimal = Field(default_factory=Decimal)


class ReportTrendResponse(BaseModel):
    """Daily income/expense series for the period (for the line chart)."""

    start_date: datetime
    end_date: datetime  # exclusive upper bound
    points: list[TrendPoint] = Field(default_factory=list)
