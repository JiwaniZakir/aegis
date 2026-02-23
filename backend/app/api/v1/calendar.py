"""Calendar, meeting, contact, and briefing endpoints."""

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


class ContactCreateRequest(BaseModel):
    name: str
    source: str
    email: str | None = None
    phone: str | None = None
    category: str | None = None
    company: str | None = None
    industry: str | None = None


class ContactEdgeRequest(BaseModel):
    contact_a_id: str
    contact_b_id: str
    relationship_type: str
    weight: float = 1.0


class ContactMergeRequest(BaseModel):
    contact_ids: list[str]


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
# Contact graph endpoints
# ---------------------------------------------------------------------------


@router.post("/contacts")
async def create_contact(
    body: ContactCreateRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Add a new contact to the relationship graph."""
    from app.services.contact_graph import add_contact

    contact = await add_contact(
        db,
        str(user.id),
        name=body.name,
        source=body.source,
        email=body.email,
        phone=body.phone,
        category=body.category,
        company=body.company,
        industry=body.industry,
    )
    await db.commit()
    return contact


@router.post("/contacts/edge")
async def create_contact_edge(
    body: ContactEdgeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Create a relationship edge between two contacts."""
    from app.services.contact_graph import add_edge

    edge = await add_edge(
        db,
        str(user.id),
        contact_a_id=body.contact_a_id,
        contact_b_id=body.contact_b_id,
        relationship_type=body.relationship_type,
        weight=body.weight,
    )
    await db.commit()
    return edge


@router.post("/contacts/merge")
async def merge_contacts(
    body: ContactMergeRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Merge duplicate contacts into one."""
    from app.services.contact_graph import merge_contacts as do_merge

    result = await do_merge(db, str(user.id), body.contact_ids)
    await db.commit()
    return result


@router.get("/contacts/graph")
async def get_contact_graph(
    center_id: str = Query(..., description="Contact ID to center the graph on"),
    depth: int = Query(2, ge=1, le=5),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get network graph around a contact for visualization."""
    from app.services.contact_graph import get_network_graph

    return await get_network_graph(db, str(user.id), center_id, depth=depth)


@router.get("/contacts/shortest-path")
async def get_shortest_path(
    from_id: str = Query(...),
    to_id: str = Query(...),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Find shortest path between two contacts for warm intros."""
    from app.services.contact_graph import shortest_path

    try:
        path = await shortest_path(db, str(user.id), from_id, to_id)
        return {"path": path, "hops": len(path) - 1}
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.get("/contacts/suggest-outreach")
async def get_outreach_suggestions(
    limit: int = Query(10, ge=1, le=50),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Suggest contacts to reconnect with based on relationship decay."""
    from app.services.contact_graph import suggest_outreach

    return await suggest_outreach(db, str(user.id), limit=limit)


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
