"""News aggregation — NewsAPI + RSS feed parsing for content discovery."""

from __future__ import annotations

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.security.url_validator import validate_url

logger = structlog.get_logger()

_NEWSAPI_BASE = "https://newsapi.org/v2"


class NewsAggregatorError(Exception):
    """Raised when news aggregation fails."""


class NewsAggregator(BaseIntegration):
    """Multi-source news aggregation: NewsAPI + RSS feeds."""

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._newsapi_key = settings.newsapi_key

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def get_top_headlines(
        self,
        *,
        category: str = "technology",
        country: str = "us",
        page_size: int = 20,
    ) -> list[dict]:
        """Fetch top headlines from NewsAPI.

        Args:
            category: business, entertainment, general, health, science, sports, technology.
            country: Two-letter ISO country code.
            page_size: Number of articles (max 100).

        Returns:
            List of article dicts.
        """
        if not self._newsapi_key:
            self._log.warning("newsapi_key_not_configured")
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{_NEWSAPI_BASE}/top-headlines",
                headers={"X-Api-Key": self._newsapi_key},
                params={
                    "category": category,
                    "country": country,
                    "pageSize": min(page_size, 100),
                },
            )
            response.raise_for_status()
            data = response.json()

        articles = _parse_newsapi_articles(data.get("articles", []))

        self._log.info("newsapi_headlines_fetched", category=category, count=len(articles))
        await self._audit(
            action="newsapi_headlines_fetch",
            resource_type="news",
            metadata={"category": category, "count": len(articles)},
        )
        return articles

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def search_news(
        self,
        query: str,
        *,
        sort_by: str = "relevancy",
        page_size: int = 20,
    ) -> list[dict]:
        """Search news articles via NewsAPI.

        Args:
            query: Search query.
            sort_by: relevancy, popularity, or publishedAt.
            page_size: Number of articles.

        Returns:
            List of article dicts.
        """
        if not self._newsapi_key:
            self._log.warning("newsapi_key_not_configured")
            return []

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{_NEWSAPI_BASE}/everything",
                headers={"X-Api-Key": self._newsapi_key},
                params={
                    "q": query,
                    "sortBy": sort_by,
                    "pageSize": min(page_size, 100),
                    "language": "en",
                },
            )
            response.raise_for_status()
            data = response.json()

        articles = _parse_newsapi_articles(data.get("articles", []))

        self._log.info("newsapi_search_fetched", query=query, count=len(articles))
        await self._audit(
            action="newsapi_search",
            resource_type="news",
            metadata={"query": query, "count": len(articles)},
        )
        return articles

    async def fetch_rss_feed(self, feed_url: str) -> list[dict]:
        """Parse an RSS feed and return structured articles.

        Args:
            feed_url: URL of the RSS feed.

        Returns:
            List of article dicts.

        Raises:
            SSRFError: If the feed URL targets a private/internal resource.
        """
        validate_url(feed_url)

        try:
            import feedparser
        except ImportError as exc:
            msg = "feedparser is required. Install with: uv add feedparser"
            raise NewsAggregatorError(msg) from exc

        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(feed_url)
            response.raise_for_status()

        feed = feedparser.parse(response.text)
        articles = []

        for entry in feed.entries[:50]:
            published = ""
            if hasattr(entry, "published"):
                published = entry.published
            elif hasattr(entry, "updated"):
                published = entry.updated

            articles.append(
                {
                    "title": getattr(entry, "title", ""),
                    "description": getattr(entry, "summary", "")[:500],
                    "url": getattr(entry, "link", ""),
                    "published_at": published,
                    "source": feed.feed.get("title", feed_url),
                    "author": getattr(entry, "author", ""),
                }
            )

        self._log.info("rss_feed_fetched", url=feed_url, count=len(articles))
        await self._audit(
            action="rss_feed_fetch",
            resource_type="news",
            metadata={"url": feed_url, "count": len(articles)},
        )
        return articles

    async def aggregate_feeds(self, feed_urls: list[str]) -> list[dict]:
        """Aggregate articles from multiple RSS feeds."""
        all_articles: list[dict] = []
        for url in feed_urls:
            try:
                articles = await self.fetch_rss_feed(url)
                all_articles.extend(articles)
            except Exception as exc:
                self._log.warning("rss_feed_failed", url=url, error=str(type(exc).__name__))

        # Sort by published date (newest first)
        all_articles.sort(key=lambda a: a.get("published_at", ""), reverse=True)
        return all_articles

    async def sync(self) -> None:
        """Pull latest news headlines."""
        await self.get_top_headlines()

    async def health_check(self) -> bool:
        """Verify NewsAPI key is valid."""
        try:
            articles = await self.get_top_headlines(page_size=1)
            return len(articles) > 0
        except Exception:
            self._log.warning("newsapi_health_check_failed")
            return False


def _parse_newsapi_articles(articles: list[dict]) -> list[dict]:
    """Parse NewsAPI article objects into clean dicts."""
    parsed = []
    for article in articles:
        source = article.get("source", {})
        parsed.append(
            {
                "title": article.get("title", ""),
                "description": (
                    article.get("description", "")[:500] if article.get("description") else ""
                ),
                "url": article.get("url", ""),
                "image_url": article.get("urlToImage", ""),
                "published_at": article.get("publishedAt", ""),
                "source": source.get("name", ""),
                "author": article.get("author", ""),
            }
        )
    return parsed
