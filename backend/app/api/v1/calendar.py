"""Calendar, meeting, and briefing endpoints."""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, UploadFile
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User

logger = structlog.get_logger()

router = APIRouter(tags=["calendar"])


# ---------------------------------------------------------------------------
# Pydantic request schemas
# ---------------------------------------------------------------------------


class MeetingUploadRequest(BaseModel):
    title: str
    start_time: datetime


# ---------------------------------------------------------------------------
# Calendar endpoints
# ---------------------------------------------------------------------------


@router.get("/calendar/today")
async def get_today_events(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Today's aggregated events from all calendar sources."""
    from app.services.daily_briefing import get_today_calendar

    return await get_today_calendar(db, str(user.id))


@router.get("/calendar/events")
async def get_events(
    days: int = Query(7, ge=1, le=90),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Calendar events for the next N days from all sources."""
    from datetime import timedelta

    events: list[dict] = []
    start = datetime.now(UTC)
    end = start + timedelta(days=days)

    try:
        from app.integrations.google_calendar_client import GoogleCalendarClient

        gcal = GoogleCalendarClient(str(user.id), db)
        events.extend(await gcal.get_events(start=start, end=end))
    except Exception as exc:
        logger.warning("gcal_fetch_failed", error=str(type(exc).__name__))

    try:
        from app.integrations.outlook_client import OutlookClient

        outlook = OutlookClient(str(user.id), db)
        events.extend(await outlook.get_events(start=start, end=end))
    except Exception as exc:
        logger.warning("outlook_fetch_failed", error=str(type(exc).__name__))

    events.sort(key=lambda e: e.get("start", ""))
    return {"events": events, "count": len(events), "days": days}


# ---------------------------------------------------------------------------
# Meeting endpoints
# ---------------------------------------------------------------------------


@router.post("/meetings/upload")
async def upload_meeting(
    audio: UploadFile,
    title: str = Query("Untitled Meeting"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Upload a meeting audio file for transcription and summarization."""
    import tempfile
    from pathlib import Path

    from app.services.meeting_transcriber import (
        store_meeting,
        summarize_meeting,
        transcribe,
    )

    # Save audio to temp file
    suffix = Path(audio.filename or "audio.wav").suffix or ".wav"
    with tempfile.NamedTemporaryFile(suffix=suffix, delete=False) as tmp:
        content = await audio.read()
        tmp.write(content)
        tmp_path = tmp.name

    transcript = await transcribe(tmp_path)
    summary = await summarize_meeting(db, str(user.id), transcript, meeting_title=title)

    meeting_id = await store_meeting(
        db,
        str(user.id),
        title=title,
        start_time=datetime.now(UTC),
        transcript=transcript,
        summary=summary,
        source="upload",
    )
    await db.commit()

    return {"meeting_id": meeting_id, "summary": summary}


@router.get("/meetings/{meeting_id}/summary")
async def get_meeting_summary(
    meeting_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the summary and action items for a specific meeting."""
    from sqlalchemy import select

    from app.models.meeting import Meeting

    try:
        mid = uuid.UUID(meeting_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid meeting ID") from exc

    result = await db.execute(
        select(Meeting).where(
            Meeting.id == mid,
            Meeting.user_id == user.id,
        )
    )
    meeting = result.scalar_one_or_none()
    if not meeting:
        raise HTTPException(status_code=404, detail="Meeting not found")

    return {
        "id": str(meeting.id),
        "title": meeting.title,
        "start_time": meeting.start_time.isoformat(),
        "end_time": meeting.end_time.isoformat() if meeting.end_time else None,
        "summary": meeting.summary,
        "action_items": meeting.action_items,
        "attendees": meeting.attendees,
    }


# ---------------------------------------------------------------------------
# Briefing endpoint
# ---------------------------------------------------------------------------


@router.get("/briefing/today")
async def get_today_briefing(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Generate or retrieve today's morning briefing."""
    from app.services.daily_briefing import generate_morning_brief

    briefing = await generate_morning_brief(db, str(user.id))
    await db.commit()
    return briefing
