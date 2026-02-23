"""Email and assignment endpoints — digests, categorization, LMS tracking."""

from __future__ import annotations

import structlog
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.services.assignment_tracker import (
    generate_reminders,
    get_overdue_assignments,
    get_upcoming_assignments,
)
from app.services.email_analyzer import (
    daily_email_digest,
    spam_audit,
    weekly_email_digest,
)

logger = structlog.get_logger()

router = APIRouter(tags=["email"])


# ---------------------------------------------------------------------------
# Email endpoints
# ---------------------------------------------------------------------------


@router.get("/email/digest")
async def get_daily_digest(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Daily email digest — categorized summary of today's emails."""
    return await daily_email_digest(db, str(user.id))


@router.get("/email/weekly")
async def get_weekly_digest(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Weekly email productivity report."""
    return await weekly_email_digest(db, str(user.id))


@router.get("/email/spam-audit")
async def get_spam_audit(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Identify promotional/junk senders recommended for unsubscription."""
    return await spam_audit(db, str(user.id))


# ---------------------------------------------------------------------------
# Assignment endpoints
# ---------------------------------------------------------------------------


@router.get("/assignments/upcoming")
async def get_upcoming(
    days: int = Query(14, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Upcoming assignments from all LMS platforms, sorted by due date."""
    return await get_upcoming_assignments(db, str(user.id), days=days)


@router.get("/assignments/overdue")
async def get_overdue(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Overdue assignments from all LMS platforms."""
    return await get_overdue_assignments(db, str(user.id))


@router.get("/assignments/reminders")
async def get_reminders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Prioritized assignment reminders based on urgency."""
    return await generate_reminders(db, str(user.id))
