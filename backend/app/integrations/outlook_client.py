"""Outlook Calendar integration — event fetching via Microsoft Graph API."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration

logger = structlog.get_logger()

_GRAPH_API_BASE = "https://graph.microsoft.com/v1.0"
_MS_TOKEN_URL = "https://login.microsoftonline.com/{tenant}/oauth2/v2.0/token"  # noqa: S105


class OutlookClient(BaseIntegration):
    """Microsoft Outlook/Graph Calendar integration.

    Same interface as GoogleCalendarClient for consistent aggregation.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._client_id = settings.azure_client_id
        self._client_secret = settings.azure_client_secret
        self._tenant_id = settings.azure_tenant_id

    async def _get_access_token(self) -> str:
        """Get a valid access token, refreshing if needed."""
        try:
            return await self.get_credential("outlook_access_token")
        except KeyError:
            return await self._refresh_access_token()

    async def _refresh_access_token(self) -> str:
        """Refresh the Microsoft OAuth access token."""
        refresh_token = await self.get_credential("outlook_refresh_token")
        token_url = _MS_TOKEN_URL.format(tenant=self._tenant_id or "common")

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                token_url,
                data={
                    "grant_type": "refresh_token",
                    "refresh_token": refresh_token,
                    "client_id": self._client_id,
                    "client_secret": self._client_secret,
                    "scope": "Calendars.Read",
                },
            )
            response.raise_for_status()
            data = response.json()

        await self.store_credential("outlook_access_token", data["access_token"])
        if "refresh_token" in data:
            await self.store_credential("outlook_refresh_token", data["refresh_token"])
        return data["access_token"]

    async def _api_request(self, path: str, *, params: dict | None = None) -> dict:
        """Make an authenticated GET request to the Microsoft Graph API."""
        access_token = await self._get_access_token()
        url = f"{_GRAPH_API_BASE}{path}"
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

        Same interface as GoogleCalendarClient.get_events().
        """
        if start is None:
            start = datetime.now(UTC)
        if end is None:
            end = start + timedelta(days=7)

        data = await self._api_request(
            "/me/calendarView",
            params={
                "startDateTime": start.isoformat(),
                "endDateTime": end.isoformat(),
                "$top": 100,
                "$orderby": "start/dateTime",
            },
        )

        events = []
        for item in data.get("value", []):
            events.append(_parse_outlook_event(item))

        self._log.info("outlook_events_fetched", count=len(events))
        await self._audit(
            action="outlook_events_fetch",
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
        """Verify Outlook credentials."""
        try:
            await self.get_events(
                start=datetime.now(UTC),
                end=datetime.now(UTC) + timedelta(hours=1),
            )
            return True
        except Exception:
            self._log.warning("outlook_health_check_failed")
            return False


def _parse_outlook_event(item: dict) -> dict:
    """Parse a Microsoft Graph Calendar event into the same format as Google."""
    start = item.get("start", {})
    end = item.get("end", {})
    attendees = item.get("attendees", [])

    return {
        "id": item.get("id", ""),
        "title": item.get("subject", "(no title)"),
        "description": item.get("bodyPreview", ""),
        "start": start.get("dateTime", ""),
        "end": end.get("dateTime", ""),
        "location": item.get("location", {}).get("displayName", ""),
        "attendees": [
            {
                "email": a.get("emailAddress", {}).get("address", ""),
                "name": a.get("emailAddress", {}).get("name", ""),
                "response": a.get("status", {}).get("response", ""),
            }
            for a in attendees
        ],
        "organizer": (item.get("organizer", {}).get("emailAddress", {}).get("address", "")),
        "status": item.get("showAs", ""),
        "html_link": item.get("webLink", ""),
    }
