"""Productivity and screen-time endpoints."""

from __future__ import annotations

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["productivity"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ScreenTimeIngestRequest(BaseModel):
    data: list[dict] = Field(min_length=1, max_length=1000)


# ---------------------------------------------------------------------------
# Productivity endpoints
# ---------------------------------------------------------------------------


@router.get("/productivity/summary")
async def get_productivity_summary(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get aggregated productivity summary over a time period."""
    from app.services.productivity_analyzer import (
        get_productivity_summary as do_summary,
    )

    return await do_summary(db, str(user.id), days=days)


@router.post("/productivity/screen-time")
async def ingest_screen_time(
    body: ScreenTimeIngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingest screen time data from Mac/iPhone agents."""
    from app.services.productivity_analyzer import ingest_screen_time as do_ingest

    result = await do_ingest(db, str(user.id), body.data)
    await db.commit()
    return result


@router.get("/productivity/daily")
async def get_daily_productivity(
    target_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get daily productivity summary."""
    from app.services.productivity_analyzer import get_daily_productivity as get_daily

    return await get_daily(db, str(user.id), target_date)


@router.get("/productivity/trends")
async def get_productivity_trends(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get productivity trends over time."""
    from app.services.productivity_analyzer import get_productivity_trends as get_trends

    return await get_trends(db, str(user.id), days=days)


@router.get("/productivity/weekly")
async def get_weekly_report(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get weekly productivity report."""
    from app.services.productivity_analyzer import get_weekly_report

    return await get_weekly_report(db, str(user.id))


@router.get("/productivity/app-usage")
async def get_app_usage(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get app-level usage breakdown."""
    from app.services.productivity_analyzer import get_app_usage_breakdown

    return await get_app_usage_breakdown(db, str(user.id), days=days)
