"""WhatsApp Web bridge integration via whatsapp-web.js sidecar."""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.base import BaseIntegration

logger = structlog.get_logger()


class WhatsAppBridgeError(Exception):
    """Raised when WhatsApp bridge communication fails."""


class WhatsAppBridgeClient(BaseIntegration):
    """Client for the whatsapp-web.js Node.js sidecar bridge.

    The bridge runs as a Docker sidecar container and exposes a local HTTP API
    for reading conversations, fetching messages, and sending replies. All
    traffic stays on the internal Docker network — no public exposure.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self.base_url = settings.whatsapp_bridge_url

    async def health_check(self) -> bool:
        """Check if the WhatsApp bridge sidecar is reachable and authenticated."""
        try:
            async with httpx.AsyncClient(timeout=5.0) as client:
                resp = await client.get(f"{self.base_url}/health")
                return resp.status_code == 200
        except (httpx.RequestError, httpx.HTTPError):
            self._log.warning("whatsapp_bridge_unreachable")
            return False

    async def sync(self) -> None:
        """Pull recent messages from the bridge.

        Called by the Celery task on schedule. Delegates to
        ``get_recent_messages`` which handles the HTTP communication.
        """
        await self._audit(
            action="sync_start",
            resource_type="whatsapp",
            detail="Starting WhatsApp message sync",
        )
        messages = await self.get_recent_messages(limit=100)
        await self._audit(
            action="sync_complete",
            resource_type="whatsapp",
            detail=f"Fetched {len(messages)} messages from bridge",
        )

    async def get_recent_messages(self, limit: int = 50) -> list[dict]:
        """Fetch recent messages from the WhatsApp bridge.

        Args:
            limit: Maximum number of messages to retrieve.

        Returns:
            List of message dicts from the bridge API.

        Raises:
            WhatsAppBridgeError: If the bridge request fails.
        """
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                resp = await client.get(
                    f"{self.base_url}/messages",
                    params={"limit": limit},
                )
                resp.raise_for_status()
                data: list[dict] = resp.json()
                self._log.info("whatsapp_messages_fetched", count=len(data))
                return data
        except httpx.HTTPStatusError as exc:
            self._log.error(
                "whatsapp_bridge_http_error",
                status_code=exc.response.status_code,
                error=str(exc),
            )
            raise WhatsAppBridgeError(f"Bridge returned HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            self._log.error("whatsapp_bridge_request_error", error=str(exc))
            raise WhatsAppBridgeError(f"Failed to fetch messages: {exc}") from exc

    async def send_message(self, phone: str, message: str) -> dict:
        """Send a WhatsApp message via the bridge.

        Args:
            phone: Recipient phone number (with country code).
            message: Message body to send.

        Returns:
            Response dict from the bridge API.

        Raises:
            WhatsAppBridgeError: If the send request fails.
        """
        # Log with redacted phone for privacy
        safe_phone = phone[:4] + "****" if len(phone) > 4 else "****"
        self._log.info("whatsapp_send_attempt", phone=safe_phone)

        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.post(
                    f"{self.base_url}/send",
                    json={"phone": phone, "message": message},
                )
                resp.raise_for_status()
                await self._audit(
                    action="whatsapp_send",
                    resource_type="whatsapp_message",
                    detail=f"Message sent to {safe_phone}",
                )
                result: dict = resp.json()
                return result
        except httpx.HTTPStatusError as exc:
            self._log.error(
                "whatsapp_send_http_error",
                phone=safe_phone,
                status_code=exc.response.status_code,
            )
            raise WhatsAppBridgeError(f"Send failed with HTTP {exc.response.status_code}") from exc
        except httpx.RequestError as exc:
            self._log.error("whatsapp_send_request_error", phone=safe_phone, error=str(exc))
            raise WhatsAppBridgeError(f"Failed to send message: {exc}") from exc

    async def get_conversations(self) -> list[dict]:
        """Fetch the list of conversations from the bridge.

        Returns:
            List of conversation dicts from the bridge API.

        Raises:
            WhatsAppBridgeError: If the request fails.
        """
        try:
            async with httpx.AsyncClient(timeout=15.0) as client:
                resp = await client.get(f"{self.base_url}/conversations")
                resp.raise_for_status()
                data: list[dict] = resp.json()
                self._log.info("whatsapp_conversations_fetched", count=len(data))
                return data
        except httpx.HTTPStatusError as exc:
            self._log.error(
                "whatsapp_conversations_http_error",
                status_code=exc.response.status_code,
            )
            raise WhatsAppBridgeError(
                f"Conversations fetch failed with HTTP {exc.response.status_code}"
            ) from exc
        except httpx.RequestError as exc:
            self._log.error("whatsapp_conversations_request_error", error=str(exc))
            raise WhatsAppBridgeError(f"Failed to fetch conversations: {exc}") from exc
