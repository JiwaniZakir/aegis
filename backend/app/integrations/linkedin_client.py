"""LinkedIn integration — posting via official API, feed reading via scraper.

The official LinkedIn API only supports posting (with approved app).
Feed reading requires browser automation, which is against ToS.
Rate limiting and stealth measures are mandatory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.content import ContentPost

logger = structlog.get_logger()

_LINKEDIN_API_BASE = "https://api.linkedin.com/v2"
_LINKEDIN_POST_URL = "https://api.linkedin.com/rest/posts"


class LinkedInClientError(Exception):
    """Raised when LinkedIn API operations fail."""


class LinkedInClient(BaseIntegration):
    """LinkedIn integration for posting and limited feed reading.

    Official API: posting only (requires approved LinkedIn app).
    Feed reading: not available via official API — placeholder for scraper.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._access_token = settings.linkedin_access_token

    async def _get_access_token(self) -> str:
        """Get a valid LinkedIn access token."""
        if self._access_token:
            return self._access_token
        try:
            return await self.get_credential("linkedin_access_token")
        except KeyError as exc:
            msg = "LinkedIn access token not configured"
            raise LinkedInClientError(msg) from exc

    async def _api_request(
        self,
        method: str,
        url: str,
        *,
        json_data: dict | None = None,
        params: dict | None = None,
    ) -> dict:
        """Make an authenticated request to the LinkedIn API."""
        access_token = await self._get_access_token()
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json",
            "X-Restli-Protocol-Version": "2.0.0",
            "LinkedIn-Version": "202401",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.request(
                method, url, headers=headers, json=json_data, params=params
            )
            response.raise_for_status()
            if response.content:
                return response.json()
            return {}

    async def get_profile(self) -> dict:
        """Get the authenticated user's LinkedIn profile."""
        data = await self._api_request("GET", f"{_LINKEDIN_API_BASE}/userinfo")
        return {
            "id": data.get("sub", ""),
            "name": data.get("name", ""),
            "email": data.get("email", ""),
            "picture": data.get("picture", ""),
        }

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def create_post(
        self,
        text: str,
        *,
        visibility: str = "PUBLIC",
    ) -> dict:
        """Create a text post on LinkedIn via the official API.

        Args:
            text: Post content (max 3000 characters).
            visibility: PUBLIC, CONNECTIONS, or LOGGED_IN.

        Returns:
            Dict with post ID and status.
        """
        if len(text) > 3000:
            text = text[:2997] + "..."

        profile = await self.get_profile()
        author_urn = f"urn:li:person:{profile['id']}"

        post_data = {
            "author": author_urn,
            "commentary": text,
            "visibility": visibility,
            "distribution": {
                "feedDistribution": "MAIN_FEED",
                "targetEntities": [],
                "thirdPartyDistributionChannels": [],
            },
            "lifecycleState": "PUBLISHED",
        }

        result = await self._api_request("POST", _LINKEDIN_POST_URL, json_data=post_data)

        self._log.info("linkedin_post_created")
        await self._audit(
            action="linkedin_post_create",
            resource_type="content",
            metadata={"text_length": len(text), "visibility": visibility},
        )

        return {
            "post_id": result.get("id", ""),
            "status": "published",
            "platform": "linkedin",
        }

    async def store_post(self, post_result: dict, content: str) -> str:
        """Store a LinkedIn post in the database."""
        uid = uuid.UUID(self.user_id)
        post = ContentPost(
            user_id=uid,
            platform="linkedin",
            content=content,
            posted_at=datetime.now(UTC),
            status="published",
            external_post_id=post_result.get("post_id", ""),
        )
        self.db.add(post)
        await self.db.flush()
        return str(post.id)

    async def get_feed(self, limit: int = 20) -> list[dict]:
        """Get LinkedIn feed posts.

        NOTE: The official LinkedIn API does not support reading feed posts
        for personal accounts. This returns a placeholder.
        Browser automation (Playwright) would be needed for actual feed reading,
        which is against LinkedIn ToS.
        """
        self._log.warning("linkedin_feed_not_available_via_api")
        return []

    async def sync(self) -> None:
        """Pull latest LinkedIn data (limited by API)."""
        await self.get_profile()

    async def health_check(self) -> bool:
        """Verify LinkedIn credentials are valid."""
        try:
            await self.get_profile()
            return True
        except Exception:
            self._log.warning("linkedin_health_check_failed")
            return False
