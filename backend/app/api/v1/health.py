"""Health and fitness endpoints."""

from __future__ import annotations

from datetime import date

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["health"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class AppleHealthIngestRequest(BaseModel):
    data: list[dict] = Field(min_length=1, max_length=10000)


class GroceryListRequest(BaseModel):
    days: int = Field(default=7, ge=1, le=30)


# ---------------------------------------------------------------------------
# Health-data endpoints (prefixed with /health-data/ to avoid collision
# with the root /health liveness check)
# ---------------------------------------------------------------------------


@router.get("/health-data/summary")
async def get_health_summary(
    target_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get daily health summary with all metrics."""
    from app.services.health_optimizer import get_daily_health_summary

    return await get_daily_health_summary(db, str(user.id), target_date)


@router.get("/health-data/trends")
async def get_health_trends(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get health metric trends over time."""
    from app.services.health_optimizer import get_health_trends as do_trends

    return await do_trends(db, str(user.id), days=days)


@router.get("/health-data/goals")
async def get_health_goals(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Check today's health metrics against configured goals."""
    from app.services.health_optimizer import check_health_goals

    return await check_health_goals(db, str(user.id))


@router.post("/health-data/apple")
async def ingest_apple_health(
    body: AppleHealthIngestRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Ingest Apple Health data exported via iOS Shortcuts."""
    from app.services.health_optimizer import ingest_apple_health as do_ingest

    result = await do_ingest(db, str(user.id), body.data)
    await db.commit()
    return result


@router.post("/health-data/grocery-list")
async def generate_grocery_list(
    body: GroceryListRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate a grocery list based on macro goals."""
    from app.services.health_optimizer import generate_grocery_list as gen_list

    return await gen_list(db, str(user.id))


@router.get("/health-data/weekly")
async def get_weekly_health_trends(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get weekly health trends with daily breakdowns."""
    from app.services.health_optimizer import get_weekly_trends

    return await get_weekly_trends(db, str(user.id))


@router.get("/health-data/macros")
async def get_macros(
    target_date: date | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get macro tracking vs daily targets."""
    from app.services.health_optimizer import get_macro_tracking

    return await get_macro_tracking(db, str(user.id), target_date)


@router.get("/health-data/recommendations")
async def get_recommendations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get personalised health recommendations."""
    from app.services.health_optimizer import generate_recommendations

    return await generate_recommendations(db, str(user.id))
