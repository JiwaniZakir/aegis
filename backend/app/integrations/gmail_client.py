"""Gmail integration — read-only email fetching via Gmail API."""

from __future__ import annotations

import base64
import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.email_digest import EmailDigest
from app.security.encryption import encrypt_field

logger = structlog.get_logger()

_GMAIL_API_BASE = "https://gmail.googleapis.com/gmail/v1"
_GOOGLE_TOKEN_URL = "https://oauth2.googleapis.com/token"  # noqa: S105


class GmailClient(BaseIntegration):
    """Read-only Gmail integration via OAuth 2.0.

    NEVER sends, deletes, or modifies emails. Only reads.
    """

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
        self._log.debug("google_token_refreshed")
        return data["access_token"]

    async def _api_request(
        self,
        method: str,
        path: str,
        *,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the Gmail API with auto-retry on 401."""
        access_token = await self._get_access_token()
        url = f"{_GMAIL_API_BASE}{path}"
        headers = {"Authorization": f"Bearer {access_token}"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(method, url, headers=headers, params=params)

            if response.status_code == 401:
                access_token = await self._refresh_access_token()
                headers["Authorization"] = f"Bearer {access_token}"
                response = await client.request(method, url, headers=headers, params=params)

            response.raise_for_status()
            return response.json() if response.content else {}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def fetch_new_emails(self, since: str | None = None) -> list[dict]:
        """Fetch new emails since the given timestamp.

        Args:
            since: RFC 3339 date string or Gmail query date (e.g. "2024/01/01").
                   Defaults to last 24 hours.

        Returns:
            List of email summary dicts (no raw body — bodies stored encrypted).
        """
        query = "is:inbox"
        if since:
            query += f" after:{since}"

        data = await self._api_request(
            "GET",
            "/users/me/messages",
            params={"q": query, "maxResults": 100},
        )

        messages = data.get("messages", [])
        results = []

        for msg_ref in messages:
            msg_id = msg_ref["id"]
            try:
                email_data = await self._get_email_detail(msg_id)
                if email_data:
                    results.append(email_data)
            except httpx.HTTPStatusError:
                self._log.warning("gmail_message_fetch_failed", message_id=msg_id)

        self._log.info("gmail_emails_fetched", count=len(results))
        await self._audit(
            action="gmail_fetch",
            resource_type="email",
            metadata={"count": len(results)},
        )
        return results

    async def _get_email_detail(self, message_id: str) -> dict | None:
        """Fetch a single email's headers and snippet."""
        data = await self._api_request(
            "GET",
            f"/users/me/messages/{message_id}",
            params={"format": "metadata", "metadataHeaders": "Subject,From,Date"},
        )

        headers = {h["name"]: h["value"] for h in data.get("payload", {}).get("headers", [])}
        subject = headers.get("Subject", "(no subject)")
        sender = headers.get("From", "unknown")
        date_str = headers.get("Date", "")
        snippet = data.get("snippet", "")

        return {
            "message_id": message_id,
            "subject": subject,
            "sender": sender,
            "date": date_str,
            "snippet": snippet,
            "labels": data.get("labelIds", []),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_email_body(self, message_id: str) -> str:
        """Fetch full email body text for a specific message.

        The body is returned in plaintext. Caller is responsible for
        encrypting before storage.
        """
        data = await self._api_request(
            "GET",
            f"/users/me/messages/{message_id}",
            params={"format": "full"},
        )

        body = _extract_body(data.get("payload", {}))

        self._log.debug("gmail_body_fetched", message_id=message_id)
        return body

    async def list_labels(self) -> list[dict]:
        """List all Gmail labels/folders."""
        data = await self._api_request("GET", "/users/me/labels")
        labels = [
            {"id": lbl["id"], "name": lbl["name"], "type": lbl.get("type", "user")}
            for lbl in data.get("labels", [])
        ]
        return labels

    async def store_email(self, email_data: dict) -> None:
        """Store an email summary in the database with encrypted body."""
        settings = get_settings()
        uid = uuid.UUID(self.user_id)

        # Check if already stored
        existing = await self.db.execute(
            select(EmailDigest).where(EmailDigest.message_id == email_data["message_id"])
        )
        if existing.scalar_one_or_none() is not None:
            return

        encrypted_snippet = None
        if email_data.get("snippet"):
            encrypted_snippet = encrypt_field(
                email_data["snippet"],
                settings.master_key_bytes,
                context=f"email.body.{self.user_id}",
            )

        digest = EmailDigest(
            user_id=uid,
            message_id=email_data["message_id"],
            subject=email_data.get("subject", "(no subject)"),
            sender=email_data.get("sender", "unknown"),
            priority="informational",
            category="informational",
            encrypted_body_summary=encrypted_snippet,
            email_date=datetime.now(UTC),
        )
        self.db.add(digest)
        await self.db.flush()

    async def sync(self) -> None:
        """Pull latest emails and store summaries."""
        emails = await self.fetch_new_emails()
        for email in emails:
            await self.store_email(email)

    async def health_check(self) -> bool:
        """Verify Gmail credentials are valid."""
        try:
            await self.list_labels()
            return True
        except Exception:
            self._log.warning("gmail_health_check_failed")
            return False


def _extract_body(payload: dict) -> str:
    """Extract plaintext body from a Gmail message payload."""
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data", "")
        if data:
            return base64.urlsafe_b64decode(data).decode("utf-8", errors="replace")

    for part in payload.get("parts", []):
        result = _extract_body(part)
        if result:
            return result

    return ""
