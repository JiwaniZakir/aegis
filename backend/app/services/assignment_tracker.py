"""Assignment tracker — aggregates assignments from Canvas, Blackboard, Pearson."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime, timedelta

import structlog
from sqlalchemy import and_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.assignment import Assignment
from app.security.audit import audit_log

logger = structlog.get_logger()


async def get_upcoming_assignments(
    db: AsyncSession,
    user_id: str,
    *,
    days: int = 14,
) -> list[dict]:
    """Get upcoming assignments sorted by due date.

    Args:
        db: Database session.
        user_id: User UUID string.
        days: Look-ahead window in days (default 14).

    Returns:
        List of assignment dicts sorted by due date (soonest first).
    """
    uid = uuid.UUID(user_id)
    now = datetime.now(UTC)
    cutoff = now + timedelta(days=days)

    result = await db.execute(
        select(Assignment)
        .where(
            and_(
                Assignment.user_id == uid,
                Assignment.status != "completed",
                Assignment.due_date.is_not(None),
                Assignment.due_date >= now,
                Assignment.due_date <= cutoff,
            )
        )
        .order_by(Assignment.due_date.asc())
    )
    assignments = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "platform": a.platform,
            "course": a.course,
            "title": a.title,
            "due_date": str(a.due_date),
            "status": a.status,
            "type": a.assignment_type,
            "url": a.url,
            "days_until_due": (a.due_date - now).days if a.due_date else None,
        }
        for a in assignments
    ]


async def get_overdue_assignments(db: AsyncSession, user_id: str) -> list[dict]:
    """Get past-due assignments that haven't been completed.

    Returns:
        List of overdue assignment dicts sorted by how overdue they are.
    """
    uid = uuid.UUID(user_id)
    now = datetime.now(UTC)

    result = await db.execute(
        select(Assignment)
        .where(
            and_(
                Assignment.user_id == uid,
                Assignment.status.not_in(["completed", "submitted"]),
                Assignment.due_date.is_not(None),
                Assignment.due_date < now,
            )
        )
        .order_by(Assignment.due_date.asc())
    )
    assignments = result.scalars().all()

    return [
        {
            "id": str(a.id),
            "platform": a.platform,
            "course": a.course,
            "title": a.title,
            "due_date": str(a.due_date),
            "status": a.status,
            "type": a.assignment_type,
            "url": a.url,
            "days_overdue": (now - a.due_date).days if a.due_date else None,
        }
        for a in assignments
    ]


async def generate_reminders(db: AsyncSession, user_id: str) -> list[dict]:
    """Generate a prioritized reminder schedule based on due dates.

    Returns:
        List of reminder dicts with urgency level and suggested study time.
    """
    upcoming = await get_upcoming_assignments(db, user_id, days=14)
    overdue = await get_overdue_assignments(db, user_id)

    reminders = []

    # Overdue items get highest priority
    for a in overdue:
        reminders.append(
            {
                "assignment": a["title"],
                "course": a["course"],
                "platform": a["platform"],
                "urgency": "overdue",
                "due_date": a["due_date"],
                "message": f"OVERDUE ({a['days_overdue']}d): {a['title']} for {a['course']}",
            }
        )

    # Upcoming sorted by urgency
    for a in upcoming:
        days_left = a.get("days_until_due", 999)

        if days_left is None:
            urgency = "low"
        elif days_left <= 1:
            urgency = "critical"
        elif days_left <= 3:
            urgency = "high"
        elif days_left <= 7:
            urgency = "medium"
        else:
            urgency = "low"

        reminders.append(
            {
                "assignment": a["title"],
                "course": a["course"],
                "platform": a["platform"],
                "urgency": urgency,
                "due_date": a["due_date"],
                "days_left": days_left,
                "message": f"{a['title']} for {a['course']} — due in {days_left} day(s)",
            }
        )

    # Sort by urgency level
    urgency_order = {"overdue": 0, "critical": 1, "high": 2, "medium": 3, "low": 4}
    reminders.sort(key=lambda r: urgency_order.get(r["urgency"], 5))

    uid = uuid.UUID(user_id)
    await audit_log(
        db,
        action="generate_reminders",
        resource_type="assignment",
        user_id=uid,
        metadata={"reminder_count": len(reminders)},
    )

    logger.info("reminders_generated", user_id=user_id, count=len(reminders))
    return reminders
