"""Social media and news endpoints — posting, feed reading, web crawling."""

from __future__ import annotations

from typing import Literal

import structlog
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, Field, field_validator
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.user import User
from app.security.rate_limit import rate_limit
from app.security.url_validator import validate_url

logger = structlog.get_logger()

router = APIRouter(tags=["social"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PostRequest(BaseModel):
    text: str = Field(min_length=1, max_length=3000)
    platforms: list[Literal["linkedin", "x"]] = Field(default=["linkedin", "x"])


class TweetRequest(BaseModel):
    text: str = Field(min_length=1, max_length=280)


class CrawlRequest(BaseModel):
    urls: list[str] = Field(min_length=1, max_length=10)
    use_browser: bool = False

    @field_validator("urls")
    @classmethod
    def validate_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            validate_url(url)
        return v


class RSSFeedRequest(BaseModel):
    feed_urls: list[str] = Field(min_length=1, max_length=20)

    @field_validator("feed_urls")
    @classmethod
    def validate_feed_urls(cls, v: list[str]) -> list[str]:
        for url in v:
            validate_url(url)
        return v


# ---------------------------------------------------------------------------
# Social posting endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/social/post",
    dependencies=[Depends(rate_limit(limit=5, window_seconds=3600))],
)
async def cross_post(
    body: PostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Post content to multiple social platforms."""
    from app.services.social_poster import cross_post as do_cross_post

    return await do_cross_post(db, str(user.id), body.text, platforms=body.platforms)


@router.post(
    "/social/linkedin",
    dependencies=[Depends(rate_limit(limit=5, window_seconds=3600))],
)
async def post_linkedin(
    body: PostRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Post content to LinkedIn."""
    from app.services.social_poster import post_to_linkedin

    return await post_to_linkedin(db, str(user.id), body.text)


@router.post(
    "/social/x",
    dependencies=[Depends(rate_limit(limit=5, window_seconds=3600))],
)
async def post_tweet(
    body: TweetRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Post a tweet to X (Twitter)."""
    from app.services.social_poster import post_to_x

    return await post_to_x(db, str(user.id), body.text)


@router.get("/social/history")
async def get_post_history(
    platform: str | None = Query(None, pattern="^(linkedin|x)$"),
    limit: int = Query(50, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get posting history across platforms."""
    from app.services.social_poster import get_post_history as get_history

    return await get_history(db, str(user.id), platform=platform, limit=limit)


@router.get("/social/engagement")
async def get_engagement(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get engagement metrics summary across platforms."""
    from app.services.social_poster import get_engagement_summary

    return await get_engagement_summary(db, str(user.id))


# ---------------------------------------------------------------------------
# X-specific endpoints
# ---------------------------------------------------------------------------


@router.get(
    "/social/x/me",
    dependencies=[Depends(rate_limit(limit=30, window_seconds=3600))],
)
async def get_x_profile(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Get the authenticated X user profile."""
    from app.integrations.x_client import XClient

    client = XClient(str(user.id), db)
    return await client.get_me()


@router.get(
    "/social/x/search",
    dependencies=[Depends(rate_limit(limit=10, window_seconds=3600))],
)
async def search_x(
    query: str = Query(..., min_length=1, max_length=200),
    max_results: int = Query(10, ge=5, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Search recent tweets."""
    from app.integrations.x_client import XClient

    client = XClient(str(user.id), db)
    return await client.search_tweets(query, max_results=max_results)


# ---------------------------------------------------------------------------
# News endpoints
# ---------------------------------------------------------------------------


@router.get("/news/headlines")
async def get_headlines(
    category: str = Query(
        "technology",
        pattern="^(business|entertainment|general|health|science|sports|technology)$",
    ),
    country: str = Query("us", min_length=2, max_length=2),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Get top news headlines by category."""
    from app.integrations.news_aggregator import NewsAggregator

    news = NewsAggregator(str(user.id), db)
    return await news.get_top_headlines(category=category, country=country, page_size=page_size)


@router.get("/news/search")
async def search_news(
    query: str = Query(..., min_length=1, max_length=200),
    sort_by: str = Query("relevancy", pattern="^(relevancy|popularity|publishedAt)$"),
    page_size: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Search news articles."""
    from app.integrations.news_aggregator import NewsAggregator

    news = NewsAggregator(str(user.id), db)
    return await news.search_news(query, sort_by=sort_by, page_size=page_size)


@router.post("/news/rss")
async def aggregate_rss(
    body: RSSFeedRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Aggregate articles from multiple RSS feeds."""
    from app.integrations.news_aggregator import NewsAggregator

    news = NewsAggregator(str(user.id), db)
    return await news.aggregate_feeds(body.feed_urls)


# ---------------------------------------------------------------------------
# Web crawling endpoints
# ---------------------------------------------------------------------------


@router.post(
    "/crawl",
    dependencies=[Depends(rate_limit(limit=10, window_seconds=3600))],
)
async def crawl_urls(
    body: CrawlRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Crawl web pages and extract structured content."""
    from app.integrations.web_crawler import WebCrawler

    crawler = WebCrawler(str(user.id), db)
    results = []
    for url in body.urls:
        try:
            result = await crawler.fetch_page(url, use_browser=body.use_browser)
            results.append(result)
        except Exception as exc:
            logger.warning("crawl_endpoint_failed", url=url, error=str(type(exc).__name__))
            results.append({"url": url, "error": str(type(exc).__name__)})
    return results
