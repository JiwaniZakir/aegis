"""Cross-domain insights aggregation endpoints."""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["insights"])


@router.get("/insights/daily")
async def get_daily_insights(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return today's cross-domain insights summary.

    Aggregates highlights from finance, health, calendar, and email into a
    single response.  Delegates to the daily-briefing service for the heavy
    lifting and falls back gracefully if any individual source is unavailable.
    """
    user_id = str(user.id)
    insights: dict = {
        "date": datetime.now(UTC).strftime("%Y-%m-%d"),
        "generated_at": datetime.now(UTC).isoformat(),
        "finance": {},
        "health": {},
        "calendar": [],
        "email": {},
    }

    # Finance highlights
    try:
        from app.services.finance_analyzer import analyze_spending, portfolio_daily_brief

        spending = await analyze_spending(db, user_id, period="7d")
        portfolio = await portfolio_daily_brief(db, user_id)
        insights["finance"] = {
            "weekly_spending": spending.get("total", 0),
            "spending_trend_pct": spending.get("trend_pct", 0),
            "top_categories": dict(list(spending.get("categories", {}).items())[:5]),
            "portfolio_value": portfolio.get("total_balance", 0),
            "ai_insights": portfolio.get("ai_insights", ""),
        }
    except Exception as exc:
        logger.warning("insights_finance_failed", error=str(type(exc).__name__))

    # Health highlights
    try:
        from app.services.health_optimizer import get_daily_health_summary

        insights["health"] = await get_daily_health_summary(db, user_id, None)
    except Exception as exc:
        logger.warning("insights_health_failed", error=str(type(exc).__name__))

    # Calendar highlights
    try:
        from app.services.daily_briefing import get_today_calendar

        insights["calendar"] = await get_today_calendar(db, user_id)
    except Exception as exc:
        logger.warning("insights_calendar_failed", error=str(type(exc).__name__))

    # Email highlights
    try:
        from app.services.email_analyzer import daily_email_digest

        insights["email"] = await daily_email_digest(db, user_id)
    except Exception as exc:
        logger.warning("insights_email_failed", error=str(type(exc).__name__))

    logger.info("daily_insights_generated", user_id=user_id)
    return insights


@router.get("/insights/trends")
async def get_trends(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Return trend data across domains for the past *days*.

    Pulls spending trends, health trends, and productivity trends into a
    unified response so the console can render a single cross-domain chart.
    """
    user_id = str(user.id)
    trends: dict = {
        "days": days,
        "generated_at": datetime.now(UTC).isoformat(),
        "finance": {},
        "health": {},
        "productivity": {},
    }

    # Finance trends
    try:
        from app.services.finance_analyzer import analyze_spending

        spending = await analyze_spending(db, user_id, period=f"{days}d")
        trends["finance"] = {
            "total_spending": spending.get("total", 0),
            "trend_pct": spending.get("trend_pct", 0),
            "categories": spending.get("categories", {}),
        }
    except Exception as exc:
        logger.warning("trends_finance_failed", error=str(type(exc).__name__))

    # Health trends
    try:
        from app.services.health_optimizer import get_health_trends

        trends["health"] = await get_health_trends(db, user_id, days=days)
    except Exception as exc:
        logger.warning("trends_health_failed", error=str(type(exc).__name__))

    # Productivity trends
    try:
        from app.services.productivity_analyzer import get_productivity_trends

        trends["productivity"] = await get_productivity_trends(db, user_id, days=days)
    except Exception as exc:
        logger.warning("trends_productivity_failed", error=str(type(exc).__name__))

    logger.info("cross_domain_trends_generated", user_id=user_id, days=days)
    return trends
