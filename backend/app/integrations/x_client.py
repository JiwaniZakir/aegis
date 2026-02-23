"""X (Twitter) integration — posting and feed reading via X API v2.

Requires Basic tier ($100/mo) for read + write access.
Free tier is write-only with severe rate limits.
"""

from __future__ import annotations

import hashlib
import hmac
import time
import uuid
from datetime import UTC, datetime
from urllib.parse import quote

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.content import ContentPost

logger = structlog.get_logger()

_X_API_BASE = "https://api.twitter.com/2"
_X_UPLOAD_URL = "https://upload.twitter.com/1.1/media/upload.json"


class XClientError(Exception):
    """Raised when X API operations fail."""


class XClient(BaseIntegration):
    """X (Twitter) API v2 integration for posting and feed reading.

    OAuth 1.0a for user-context endpoints, Bearer token for app-only.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._api_key = settings.x_api_key
        self._api_secret = settings.x_api_secret
        self._access_token = settings.x_access_token
        self._access_token_secret = settings.x_access_token_secret
        self._bearer_token = settings.x_bearer_token

    def _oauth1_headers(self, method: str, url: str, params: dict | None = None) -> dict:
        """Generate OAuth 1.0a authorization headers."""
        oauth_params = {
            "oauth_consumer_key": self._api_key,
            "oauth_nonce": uuid.uuid4().hex,
            "oauth_signature_method": "HMAC-SHA1",
            "oauth_timestamp": str(int(time.time())),
            "oauth_token": self._access_token,
            "oauth_version": "1.0",
        }

        all_params = {**oauth_params, **(params or {})}
        param_string = "&".join(
            f"{quote(k, safe='')}={quote(str(v), safe='')}" for k, v in sorted(all_params.items())
        )
        base_string = f"{method.upper()}&{quote(url, safe='')}&{quote(param_string, safe='')}"
        signing_key = (
            f"{quote(self._api_secret, safe='')}&{quote(self._access_token_secret, safe='')}"
        )

        signature = hmac.new(signing_key.encode(), base_string.encode(), hashlib.sha1).digest()

        import base64

        oauth_params["oauth_signature"] = base64.b64encode(signature).decode()

        auth_header = "OAuth " + ", ".join(
            f'{quote(k, safe="")}="{quote(v, safe="")}"' for k, v in sorted(oauth_params.items())
        )

        return {"Authorization": auth_header}

    def _bearer_headers(self) -> dict:
        """Bearer token headers for app-only requests."""
        return {"Authorization": f"Bearer {self._bearer_token}"}

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def create_tweet(self, text: str) -> dict:
        """Post a tweet via X API v2.

        Args:
            text: Tweet content (max 280 characters).

        Returns:
            Dict with tweet ID and status.
        """
        if not self._api_key or not self._access_token:
            msg = "X API credentials not configured"
            raise XClientError(msg)

        if len(text) > 280:
            text = text[:277] + "..."

        url = f"{_X_API_BASE}/tweets"
        headers = self._oauth1_headers("POST", url)
        headers["Content-Type"] = "application/json"

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(url, headers=headers, json={"text": text})
            response.raise_for_status()
            data = response.json()

        tweet_data = data.get("data", {})
        self._log.info("x_tweet_created", tweet_id=tweet_data.get("id"))
        await self._audit(
            action="x_tweet_create",
            resource_type="content",
            metadata={"text_length": len(text), "tweet_id": tweet_data.get("id", "")},
        )

        return {
            "tweet_id": tweet_data.get("id", ""),
            "text": tweet_data.get("text", text),
            "status": "published",
            "platform": "x",
        }

    async def get_user_tweets(self, x_user_id: str, max_results: int = 10) -> list[dict]:
        """Fetch recent tweets for a user (requires Basic tier).

        Args:
            x_user_id: The X user ID.
            max_results: Number of tweets to fetch (5-100).

        Returns:
            List of tweet dicts.
        """
        if not self._bearer_token:
            self._log.warning("x_bearer_token_not_configured")
            return []

        url = f"{_X_API_BASE}/users/{x_user_id}/tweets"
        params = {
            "max_results": min(max(max_results, 5), 100),
            "tweet.fields": "created_at,public_metrics,text",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._bearer_headers(), params=params)
            response.raise_for_status()
            data = response.json()

        tweets = []
        for tweet in data.get("data", []):
            metrics = tweet.get("public_metrics", {})
            tweets.append(
                {
                    "id": tweet.get("id", ""),
                    "text": tweet.get("text", ""),
                    "created_at": tweet.get("created_at", ""),
                    "likes": metrics.get("like_count", 0),
                    "retweets": metrics.get("retweet_count", 0),
                    "replies": metrics.get("reply_count", 0),
                    "impressions": metrics.get("impression_count", 0),
                }
            )

        self._log.info("x_tweets_fetched", count=len(tweets))
        return tweets

    async def get_me(self) -> dict:
        """Get the authenticated user's X profile."""
        if not self._bearer_token:
            msg = "X bearer token not configured"
            raise XClientError(msg)

        url = f"{_X_API_BASE}/users/me"
        params = {"user.fields": "id,name,username,public_metrics,profile_image_url"}

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._bearer_headers(), params=params)
            response.raise_for_status()
            data = response.json()

        user_data = data.get("data", {})
        return {
            "id": user_data.get("id", ""),
            "name": user_data.get("name", ""),
            "username": user_data.get("username", ""),
            "followers": user_data.get("public_metrics", {}).get("followers_count", 0),
            "following": user_data.get("public_metrics", {}).get("following_count", 0),
        }

    async def search_tweets(self, query: str, max_results: int = 10) -> list[dict]:
        """Search recent tweets (requires Basic tier)."""
        if not self._bearer_token:
            return []

        url = f"{_X_API_BASE}/tweets/search/recent"
        params = {
            "query": query,
            "max_results": min(max(max_results, 10), 100),
            "tweet.fields": "created_at,public_metrics,author_id",
        }

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(url, headers=self._bearer_headers(), params=params)
            response.raise_for_status()
            data = response.json()

        return [
            {
                "id": t.get("id", ""),
                "text": t.get("text", ""),
                "author_id": t.get("author_id", ""),
                "created_at": t.get("created_at", ""),
                "metrics": t.get("public_metrics", {}),
            }
            for t in data.get("data", [])
        ]

    async def store_tweet(self, tweet_result: dict, content: str) -> str:
        """Store a published tweet in the database."""
        uid = uuid.UUID(self.user_id)
        post = ContentPost(
            user_id=uid,
            platform="x",
            content=content,
            posted_at=datetime.now(UTC),
            status="published",
            external_post_id=tweet_result.get("tweet_id", ""),
        )
        self.db.add(post)
        await self.db.flush()
        return str(post.id)

    async def sync(self) -> None:
        """Pull latest tweet engagement metrics."""
        try:
            me = await self.get_me()
            if me.get("id"):
                await self.get_user_tweets(me["id"], max_results=20)
        except Exception as exc:
            self._log.warning("x_sync_failed", error=str(type(exc).__name__))

    async def health_check(self) -> bool:
        """Verify X API credentials are valid."""
        try:
            await self.get_me()
            return True
        except Exception:
            self._log.warning("x_health_check_failed")
            return False
