"""Google Calendar integration — event fetching via Google Calendar API v3."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration

logger = structlog.get_logger()

_GCAL_API_BASE = "https://www.googleapis.com/calendar/v3"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105


class GoogleCalendarClient(BaseIntegration):
    """Read-only Google Calendar integration via OAuth 2.0."""

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._client_id = settings.google_client_id
        self._client_secret = settings.google_client_secret

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        try:
            return await self.get_credential("google_access_token")
        except KeyError:
            return await self._refresh_access_token()

    async def _refresh_access_token(self) -> str:
        """Refresh the Google OAuth access token."""
        refresh_token = await self.get_credential("google_refresh_token")
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                _GOOGLE_TOKEN_URL,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                },
            )
            response.raise_for_status()
            data = response.json()
        await self.store_credential("google_access_token", data["access_token"])
        return data["access_token"]

    async def _api_request(
        self,
        path: str,
        *,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated GET request to the Calendar API."""
        access_token = await self._get_access_token()
        url = f"{_GCAL_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=headers, params=params)
            if response.status_code == 401:
                access_token = await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                response = await client.get(url, headers=headers, params=params)
            response.raise_for_status()
            return response.json()

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_events(
        self,
        start: datetime | None = None,
        end: datetime | None = None,
    ) -> list[dict]:
        """Fetch calendar events within a date range.

        Args:
            start: Start of range (defaults to now).
            end: End of range (defaults to 7 days from now).

        Returns:
            List of event dicts with title, start, end, attendees.
        """
        if start is None:
            start = datetime.now(UTC)
        if end is None:
            end = start + timedelta(days=7)

        data = await self._api_request(
            "/calendars/primary/events",
            params={
                "timeMin": start.isoformat(),
                "timeMax": end.isoformat(),
                "singleEvents": "true",
                "orderBy": "startTime",
                "maxResults": 100,
            },
        )

        events = []
        for item in data.get("items", []):
            events.append(_parse_event(item))

        self._log.info("gcal_events_fetched", count=len(events))
        await self._audit(
            action="gcal_events_fetch",
            resource_type="calendar",
            metadata={"count": len(events)},
        )
        return events

    async def get_today_events(self) -> list[dict]:
        """Get today's calendar events."""
        today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)
        today_end = today_start + timedelta(days=1)
        return await self.get_events(start=today_start, end=today_end)

    async def sync(self) -> None:
        """Pull latest calendar events."""
        await self.get_events()

    async def health_check(self) -> bool:
        """Verify Google Calendar credentials."""
        try:
            await self.get_events(
                start=datetime.now(UTC),
                end=datetime.now(UTC) + timedelta(hours=1),
            )
            return True
        except Exception:
            self._log.warning("gcal_health_check_failed")
            return False


def _parse_event(item: dict) -> dict:
    """Parse a Google Calendar API event into a clean dict."""
    start = item.get("start", {})
    end = item.get("end", {})
    attendees = item.get("attendees", [])

    return {
        "id": item.get("id", ""),
        "title": item.get("summary", "(no title)"),
        "description": item.get("description", ""),
        "start": start.get("dateTime", start.get("date", "")),
        "end": end.get("dateTime", end.get("date", "")),
        "location": item.get("location", ""),
        "attendees": [
            {
                "email": a.get("email", ""),
                "name": a.get("displayName", ""),
                "response": a.get("responseStatus", ""),
            }
            for a in attendees
        ],
        "organizer": item.get("organizer", {}).get("email", ""),
        "status": item.get("status", ""),
        "html_link": item.get("htmlLink", ""),
    }
