"""Productivity analyzer — screen time, app usage, and focus metrics."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.health import HealthMetric
from app.security.audit import audit_log

logger = structlog.get_logger()


async def ingest_screen_time(
    db: AsyncSession,
    user_id: str,
    data: list[dict],
) -> dict:
    """Ingest screen time data from Mac/iPhone agents.

    Expected data format:
        [{"app": "Safari", "duration_min": 45, "category": "browser", "timestamp": "..."}]

    Returns:
        Dict with ingestion stats.
    """
    uid = uuid.UUID(user_id)
    stored = 0

    for entry in data:
        metric = HealthMetric(
            user_id=uid,
            metric_type="screen_time",
            value=float(entry.get("duration_min", 0)),
            unit="minutes",
            timestamp=(
                datetime.fromisoformat(entry["timestamp"])
                if "timestamp" in entry
                else datetime.now(UTC)
            ),
            source=entry.get("source", "device"),
        )
        db.add(metric)
        stored += 1

    await db.flush()

    await audit_log(
        db,
        action="screen_time_ingest",
        resource_type="productivity",
        user_id=uid,
        metadata={"entries": stored},
    )

    logger.info("screen_time_ingested", user_id=user_id, entries=stored)
    return {"stored": stored}


async def get_daily_productivity(
    db: AsyncSession,
    user_id: str,
    target_date: date | None = None,
) -> dict:
    """Get daily productivity summary.

    Returns:
        Dict with screen time breakdown, focus score, and comparisons.
    """
    uid = uuid.UUID(user_id)
    if target_date is None:
        target_date = date.today()

    day_start = datetime.combine(target_date, datetime.min.time(), tzinfo=UTC)
    day_end = day_start + timedelta(days=1)

    result = await db.execute(
        select(
            func.sum(HealthMetric.value).label("total"),
            func.count(HealthMetric.id).label("count"),
        ).where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.metric_type == "screen_time",
                HealthMetric.timestamp >= day_start,
                HealthMetric.timestamp < day_end,
            )
        )
    )
    row = result.one_or_none()

    total_minutes = float(row.total or 0) if row else 0
    entry_count = int(row.count or 0) if row else 0

    # Calculate focus score (lower screen time = higher score)
    max_productive_hours = 8
    focus_score = max(0, min(100, 100 - (total_minutes / (max_productive_hours * 60)) * 100))

    return {
        "date": str(target_date),
        "total_screen_time_minutes": round(total_minutes, 1),
        "total_screen_time_hours": round(total_minutes / 60, 1),
        "entry_count": entry_count,
        "focus_score": round(focus_score, 1),
    }


async def get_productivity_trends(
    db: AsyncSession,
    user_id: str,
    days: int = 7,
) -> list[dict]:
    """Get productivity trends over a time period.

    Returns:
        List of daily productivity summaries.
    """
    trends = []
    today = date.today()

    for i in range(days):
        target_date = today - timedelta(days=i)
        daily = await get_daily_productivity(db, user_id, target_date)
        trends.append(daily)

    trends.reverse()
    return trends


async def get_productivity_summary(
    db: AsyncSession,
    user_id: str,
    days: int = 7,
) -> dict:
    """Get an aggregated productivity summary over the given number of days.

    Combines screen time and app usage data into a single summary with
    totals, averages, and a focus score.

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        days: Number of days to summarise (default 7).

    Returns:
        Dict with screen time totals, averages, and focus score.
    """
    uid = uuid.UUID(user_id)
    today = date.today()
    cutoff_start = datetime.combine(today - timedelta(days=days), datetime.min.time(), tzinfo=UTC)
    cutoff_end = datetime.combine(today, datetime.min.time(), tzinfo=UTC) + timedelta(days=1)

    # Total screen time
    st_result = await db.execute(
        select(
            func.sum(HealthMetric.value).label("total"),
            func.count(HealthMetric.id).label("count"),
        ).where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.metric_type == "screen_time",
                HealthMetric.timestamp >= cutoff_start,
                HealthMetric.timestamp < cutoff_end,
            )
        )
    )
    st_row = st_result.one_or_none()
    total_screen_minutes = float(st_row.total or 0) if st_row else 0
    entry_count = int(st_row.count or 0) if st_row else 0

    # Total app usage
    au_result = await db.execute(
        select(
            func.sum(HealthMetric.value).label("total"),
            func.count(HealthMetric.id).label("count"),
        ).where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.metric_type == "app_usage",
                HealthMetric.timestamp >= cutoff_start,
                HealthMetric.timestamp < cutoff_end,
            )
        )
    )
    au_row = au_result.one_or_none()
    total_app_minutes = float(au_row.total or 0) if au_row else 0

    avg_daily_screen = total_screen_minutes / max(days, 1)
    max_productive_hours = 8
    focus_score = max(0, min(100, 100 - (avg_daily_screen / (max_productive_hours * 60)) * 100))

    await audit_log(
        db,
        action="productivity_summary",
        resource_type="productivity",
        user_id=uid,
        metadata={"days": days},
    )

    return {
        "period_days": days,
        "total_screen_time_minutes": round(total_screen_minutes, 1),
        "total_screen_time_hours": round(total_screen_minutes / 60, 1),
        "avg_daily_screen_time_minutes": round(avg_daily_screen, 1),
        "avg_daily_screen_time_hours": round(avg_daily_screen / 60, 1),
        "total_app_usage_minutes": round(total_app_minutes, 1),
        "entry_count": entry_count,
        "focus_score": round(focus_score, 1),
    }


async def get_app_usage_breakdown(
    db: AsyncSession,
    user_id: str,
    days: int = 7,
) -> list[dict]:
    """Get app-level usage breakdown over the given number of days.

    Queries HealthMetric rows with ``metric_type='app_usage'`` and groups
    by the ``source`` field (which stores the app name).

    Args:
        db: Async database session.
        user_id: UUID string of the user.
        days: Number of days to analyse (default 7).

    Returns:
        List of dicts sorted by total usage (descending).
    """
    uid = uuid.UUID(user_id)
    cutoff = datetime.now(UTC) - timedelta(days=days)

    rows = await db.execute(
        select(
            HealthMetric.source,
            func.sum(HealthMetric.value).label("total_minutes"),
            func.count(HealthMetric.id).label("sessions"),
        )
        .where(
            and_(
                HealthMetric.user_id == uid,
                HealthMetric.metric_type == "app_usage",
                HealthMetric.timestamp >= cutoff,
            )
        )
        .group_by(HealthMetric.source)
        .order_by(func.sum(HealthMetric.value).desc())
    )

    breakdown = []
    for row in rows:
        breakdown.append(
            {
                "app": row.source,
                "total_minutes": round(float(row.total_minutes), 1),
                "total_hours": round(float(row.total_minutes) / 60, 1),
                "sessions": row.sessions,
            }
        )

    await audit_log(
        db,
        action="app_usage_breakdown",
        resource_type="productivity",
        user_id=uid,
        metadata={"days": days, "apps": len(breakdown)},
    )

    logger.info(
        "app_usage_breakdown",
        user_id=user_id,
        days=days,
        apps=len(breakdown),
    )

    return breakdown


async def get_weekly_report(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Generate a weekly productivity report.

    Returns:
        Dict with weekly stats and comparisons.
    """
    uid = uuid.UUID(user_id)
    today = date.today()
    week_start = today - timedelta(days=7)

    trends = await get_productivity_trends(db, user_id, days=7)

    total_minutes = sum(d["total_screen_time_minutes"] for d in trends)
    avg_minutes = total_minutes / 7 if trends else 0
    avg_focus = sum(d["focus_score"] for d in trends) / 7 if trends else 0

    await audit_log(
        db,
        action="productivity_weekly_report",
        resource_type="productivity",
        user_id=uid,
    )

    return {
        "period": f"{week_start} to {today}",
        "total_screen_time_hours": round(total_minutes / 60, 1),
        "avg_daily_screen_time_hours": round(avg_minutes / 60, 1),
        "avg_focus_score": round(avg_focus, 1),
        "daily_breakdown": trends,
    }
