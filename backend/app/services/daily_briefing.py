"""Daily briefing generator — aggregates all data sources into a morning brief."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.briefing import DailyBriefing
from app.security.audit import audit_log

logger = structlog.get_logger()


async def generate_morning_brief(db: AsyncSession, user_id: str) -> dict:
    """Generate a comprehensive morning briefing aggregating all data sources.

    Combines: today's calendar, top priority emails, assignment deadlines,
    portfolio summary, health stats, contact follow-up reminders.

    Returns:
        Structured dict suitable for console rendering.
    """
    uid = uuid.UUID(user_id)
    today = date.today()

    briefing: dict = {
        "date": str(today),
        "generated_at": datetime.now(UTC).isoformat(),
        "calendar": [],
        "emails": {},
        "assignments": [],
        "finance": {},
        "contacts": [],
        "health": {},
    }

    # Calendar events
    try:
        from app.services.calendar_aggregator import get_today_calendar

        briefing["calendar"] = await get_today_calendar(db, user_id)
    except Exception as exc:
        logger.warning("briefing_calendar_failed", error=str(type(exc).__name__))
        briefing["calendar"] = []

    # Priority emails
    try:
        from app.services.email_analyzer import daily_email_digest

        briefing["emails"] = await daily_email_digest(db, user_id)
    except Exception as exc:
        logger.warning("briefing_email_failed", error=str(type(exc).__name__))
        briefing["emails"] = {}

    # Upcoming assignments
    try:
        from app.services.assignment_tracker import get_upcoming_assignments

        briefing["assignments"] = await get_upcoming_assignments(db, user_id, days=7)
    except Exception as exc:
        logger.warning("briefing_assignments_failed", error=str(type(exc).__name__))
        briefing["assignments"] = []

    # Finance summary
    try:
        from app.services.finance_analyzer import analyze_spending, portfolio_daily_brief

        spending = await analyze_spending(db, user_id, period="7d")
        portfolio = await portfolio_daily_brief(db, user_id)
        briefing["finance"] = {
            "weekly_spending": spending.get("total", 0),
            "spending_trend": spending.get("trend_pct", 0),
            "portfolio_value": portfolio.get("total_balance", 0),
        }
    except Exception as exc:
        logger.warning("briefing_finance_failed", error=str(type(exc).__name__))
        briefing["finance"] = {}

    # Contact follow-ups
    try:
        from app.services.contact_graph import suggest_outreach

        briefing["contacts"] = await suggest_outreach(db, user_id, limit=5)
    except Exception as exc:
        logger.warning("briefing_contacts_failed", error=str(type(exc).__name__))
        briefing["contacts"] = []

    # Store the briefing
    db_briefing = DailyBriefing(
        user_id=uid,
        briefing_date=today,
        finance_summary=str(briefing.get("finance", {})),
        email_summary=str(briefing.get("emails", {})),
        calendar_summary=str(briefing.get("calendar", [])),
        health_summary=str(briefing.get("health", {})),
        recommendations="",
    )
    db.add(db_briefing)
    await db.flush()

    await audit_log(
        db,
        action="daily_briefing_generate",
        resource_type="briefing",
        user_id=uid,
    )

    logger.info("morning_briefing_generated", user_id=user_id)
    return briefing


async def get_today_calendar(db: AsyncSession, user_id: str) -> list[dict]:
    """Aggregate today's events from all calendar sources."""
    events: list[dict] = []

    # Google Calendar
    try:
        from app.integrations.google_calendar_client import GoogleCalendarClient

        gcal = GoogleCalendarClient(user_id, db)
        events.extend(await gcal.get_today_events())
    except Exception as exc:
        logger.warning("gcal_today_failed", error=str(type(exc).__name__))

    # Outlook Calendar
    try:
        from app.integrations.outlook_client import OutlookClient

        outlook = OutlookClient(user_id, db)
        events.extend(await outlook.get_today_events())
    except Exception as exc:
        logger.warning("outlook_today_failed", error=str(type(exc).__name__))

    # Sort by start time
    events.sort(key=lambda e: e.get("start", ""))
    return events
