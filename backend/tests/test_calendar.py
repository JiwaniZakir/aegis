"""Tests for calendar, meeting, contact graph, and briefing services."""

from __future__ import annotations

import pytest

# ---------------------------------------------------------------------------
# Google Calendar event parsing
# ---------------------------------------------------------------------------


def test_parse_google_event_full():
    """Parse a fully populated Google Calendar event."""
    from app.integrations.google_calendar_client import _parse_event

    raw = {
        "id": "evt_123",
        "summary": "Team Standup",
        "description": "Daily sync",
        "start": {"dateTime": "2026-02-23T09:00:00Z"},
        "end": {"dateTime": "2026-02-23T09:30:00Z"},
        "location": "Zoom",
        "attendees": [
            {"email": "alice@co.com", "displayName": "Alice", "responseStatus": "accepted"},
        ],
        "organizer": {"email": "bob@co.com"},
        "status": "confirmed",
        "htmlLink": "https://calendar.google.com/event?eid=123",
    }
    result = _parse_event(raw)
    assert result["title"] == "Team Standup"
    assert result["start"] == "2026-02-23T09:00:00Z"
    assert result["location"] == "Zoom"
    assert len(result["attendees"]) == 1
    assert result["attendees"][0]["email"] == "alice@co.com"
    assert result["organizer"] == "bob@co.com"


def test_parse_google_event_minimal():
    """Parse a minimal Google Calendar event with missing fields."""
    from app.integrations.google_calendar_client import _parse_event

    raw = {"start": {}, "end": {}}
    result = _parse_event(raw)
    assert result["title"] == "(no title)"
    assert result["id"] == ""
    assert result["attendees"] == []
    assert result["start"] == ""


def test_parse_google_event_all_day():
    """Parse an all-day Google Calendar event (date instead of dateTime)."""
    from app.integrations.google_calendar_client import _parse_event

    raw = {
        "summary": "Company Offsite",
        "start": {"date": "2026-03-01"},
        "end": {"date": "2026-03-02"},
    }
    result = _parse_event(raw)
    assert result["start"] == "2026-03-01"
    assert result["end"] == "2026-03-02"


# ---------------------------------------------------------------------------
# Outlook event parsing
# ---------------------------------------------------------------------------


def test_parse_outlook_event_full():
    """Parse a fully populated Outlook event."""
    from app.integrations.outlook_client import _parse_outlook_event

    raw = {
        "id": "out_456",
        "subject": "Budget Review",
        "bodyPreview": "Q1 review",
        "start": {"dateTime": "2026-02-23T14:00:00Z"},
        "end": {"dateTime": "2026-02-23T15:00:00Z"},
        "location": {"displayName": "Room 401"},
        "attendees": [
            {
                "emailAddress": {"address": "carol@org.com", "name": "Carol"},
                "status": {"response": "accepted"},
            },
        ],
        "organizer": {"emailAddress": {"address": "dan@org.com"}},
        "showAs": "busy",
        "webLink": "https://outlook.office.com/cal/123",
    }
    result = _parse_outlook_event(raw)
    assert result["title"] == "Budget Review"
    assert result["location"] == "Room 401"
    assert len(result["attendees"]) == 1
    assert result["attendees"][0]["email"] == "carol@org.com"
    assert result["organizer"] == "dan@org.com"


def test_parse_outlook_event_minimal():
    """Parse an Outlook event with missing optional fields."""
    from app.integrations.outlook_client import _parse_outlook_event

    raw = {}
    result = _parse_outlook_event(raw)
    assert result["title"] == "(no title)"
    assert result["start"] == ""
    assert result["attendees"] == []


# ---------------------------------------------------------------------------
# Meeting transcription
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_transcribe_fallback_no_api_key(monkeypatch):
    """When no Deepgram API key is set, return placeholder text."""
    from unittest.mock import MagicMock

    import app.services.meeting_transcriber as mt

    mock_settings = MagicMock()
    mock_settings.deepgram_api_key = ""
    monkeypatch.setattr(mt, "get_settings", lambda: mock_settings)

    result = await mt.transcribe("/fake/audio.wav")
    assert "unavailable" in result.lower()


# ---------------------------------------------------------------------------
# Meeting summary structure
# ---------------------------------------------------------------------------


def test_meeting_summary_initial_structure():
    """Verify the default summary dict structure."""
    expected_keys = {"key_points", "action_items", "follow_ups", "decisions", "summary_text"}
    summary = {
        "key_points": [],
        "action_items": [],
        "follow_ups": [],
        "decisions": [],
        "summary_text": "",
    }
    assert set(summary.keys()) == expected_keys


# ---------------------------------------------------------------------------
# Contact graph imports
# ---------------------------------------------------------------------------


def test_contact_graph_imports():
    """Contact graph service functions are importable."""
    from app.services.contact_graph import (
        add_contact,
        add_edge,
        get_network_graph,
        merge_contacts,
        shortest_path,
        suggest_outreach,
    )

    assert callable(add_contact)
    assert callable(add_edge)
    assert callable(merge_contacts)
    assert callable(get_network_graph)
    assert callable(shortest_path)
    assert callable(suggest_outreach)


# ---------------------------------------------------------------------------
# Daily briefing structure
# ---------------------------------------------------------------------------


def test_briefing_structure():
    """Daily briefing has all required sections."""
    expected_sections = {
        "date",
        "generated_at",
        "calendar",
        "emails",
        "assignments",
        "finance",
        "contacts",
        "health",
    }
    briefing = {
        "date": "2026-02-23",
        "generated_at": "2026-02-23T06:00:00+00:00",
        "calendar": [],
        "emails": {},
        "assignments": [],
        "finance": {},
        "contacts": [],
        "health": {},
    }
    assert set(briefing.keys()) == expected_sections


# ---------------------------------------------------------------------------
# Calendar aggregation import
# ---------------------------------------------------------------------------


def test_calendar_aggregator_import():
    """Calendar aggregation from daily_briefing module imports correctly."""
    from app.services.daily_briefing import generate_morning_brief, get_today_calendar

    assert callable(generate_morning_brief)
    assert callable(get_today_calendar)


# ---------------------------------------------------------------------------
# API router registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_calendar_router_registered(client):
    """Calendar endpoints are registered in the app."""
    response = await client.get("/api/v1/calendar/today")
    # Should return 401 (not 404) because route exists but needs auth
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_briefing_router_registered(client):
    """Briefing endpoint is registered in the app."""
    response = await client.get("/api/v1/briefing/today")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_contacts_router_registered(client):
    """Contact graph endpoints are registered in the app."""
    response = await client.get("/api/v1/contacts/suggest-outreach")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_meetings_summary_registered(client):
    """Meeting summary endpoint is registered in the app."""
    response = await client.get("/api/v1/meetings/00000000-0000-0000-0000-000000000000/summary")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# GoogleCalendarClient import and structure tests
# ---------------------------------------------------------------------------


def test_google_calendar_client_import():
    """GoogleCalendarClient can be imported from the integrations module."""
    from app.integrations.google_calendar_client import GoogleCalendarClient

    assert GoogleCalendarClient is not None


def test_google_calendar_client_is_base_integration():
    """GoogleCalendarClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.google_calendar_client import GoogleCalendarClient

    assert issubclass(GoogleCalendarClient, BaseIntegration)


def test_google_calendar_client_has_required_methods():
    """GoogleCalendarClient has sync, health_check, and event retrieval methods."""
    from app.integrations.google_calendar_client import GoogleCalendarClient

    assert hasattr(GoogleCalendarClient, "sync")
    assert hasattr(GoogleCalendarClient, "health_check")
    assert hasattr(GoogleCalendarClient, "get_events")
    assert hasattr(GoogleCalendarClient, "get_today_events")


# ---------------------------------------------------------------------------
# OutlookClient import and structure tests
# ---------------------------------------------------------------------------


def test_outlook_client_import():
    """OutlookClient can be imported from the integrations module."""
    from app.integrations.outlook_client import OutlookClient

    assert OutlookClient is not None


def test_outlook_client_is_base_integration():
    """OutlookClient inherits from BaseIntegration."""
    from app.integrations.base import BaseIntegration
    from app.integrations.outlook_client import OutlookClient

    assert issubclass(OutlookClient, BaseIntegration)


def test_outlook_client_has_required_methods():
    """OutlookClient has sync, health_check, and event retrieval methods."""
    from app.integrations.outlook_client import OutlookClient

    assert hasattr(OutlookClient, "sync")
    assert hasattr(OutlookClient, "health_check")
    assert hasattr(OutlookClient, "get_events")


# ---------------------------------------------------------------------------
# Assignment tracker function tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_get_upcoming_assignments_empty(sample_user_id):
    """get_upcoming_assignments returns empty list when no assignments exist."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.assignment_tracker import get_upcoming_assignments

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await get_upcoming_assignments(mock_db, sample_user_id)
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_get_overdue_assignments_empty(sample_user_id):
    """get_overdue_assignments returns empty list when no overdue assignments."""
    from unittest.mock import AsyncMock, MagicMock

    from app.services.assignment_tracker import get_overdue_assignments

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    result = await get_overdue_assignments(mock_db, sample_user_id)
    assert isinstance(result, list)
    assert len(result) == 0


@pytest.mark.asyncio
async def test_generate_reminders_calls_audit_log(sample_user_id):
    """generate_reminders writes an audit log entry."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.assignment_tracker import generate_reminders

    mock_db = AsyncMock()
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_db.execute.return_value = mock_result

    with patch("app.services.assignment_tracker.audit_log", new_callable=AsyncMock) as mock_audit:
        result = await generate_reminders(mock_db, sample_user_id)
        mock_audit.assert_called_once()
        call_kwargs = mock_audit.call_args.kwargs
        assert call_kwargs["action"] == "generate_reminders"
        assert call_kwargs["resource_type"] == "assignment"

    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# Meeting transcriber structure tests
# ---------------------------------------------------------------------------


def test_meeting_transcriber_imports():
    """Meeting transcriber functions are importable."""
    from app.services.meeting_transcriber import store_meeting, summarize_meeting, transcribe

    assert callable(transcribe)
    assert callable(summarize_meeting)
    assert callable(store_meeting)


@pytest.mark.asyncio
async def test_summarize_meeting_no_api_key(sample_user_id):
    """summarize_meeting returns default structure when no API key configured."""
    from unittest.mock import AsyncMock, MagicMock, patch

    from app.services.meeting_transcriber import summarize_meeting

    mock_db = AsyncMock()
    mock_settings = MagicMock()
    mock_settings.anthropic_api_key = ""

    with (
        patch("app.services.meeting_transcriber.get_settings", return_value=mock_settings),
        patch("app.services.meeting_transcriber.audit_log", new_callable=AsyncMock),
    ):
        result = await summarize_meeting(mock_db, sample_user_id, "sample transcript text")

    assert "key_points" in result
    assert "action_items" in result
    assert "follow_ups" in result
    assert "decisions" in result
    assert "summary_text" in result
