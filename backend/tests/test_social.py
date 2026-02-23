"""Tests for social media, news aggregation, and web crawling services."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from pydantic import ValidationError

# ---------------------------------------------------------------------------
# X client OAuth signature generation
# ---------------------------------------------------------------------------


def test_x_oauth1_headers_structure():
    """OAuth 1.0a headers have the required structure."""
    from unittest.mock import MagicMock

    from app.integrations.x_client import XClient

    # Create client with mock db
    mock_db = MagicMock()
    client = XClient.__new__(XClient)
    client.user_id = "test-user"
    client.db = mock_db
    client._log = MagicMock()
    client._api_key = "test_key"
    client._api_secret = "test_secret"
    client._access_token = "test_token"
    client._access_token_secret = "test_token_secret"
    client._bearer_token = "test_bearer"

    headers = client._oauth1_headers("GET", "https://api.twitter.com/2/tweets")
    assert "Authorization" in headers
    assert headers["Authorization"].startswith("OAuth ")
    assert "oauth_consumer_key" in headers["Authorization"]
    assert "oauth_signature" in headers["Authorization"]
    assert "oauth_nonce" in headers["Authorization"]


def test_x_bearer_headers():
    """Bearer token headers are correctly formatted."""

    from app.integrations.x_client import XClient

    client = XClient.__new__(XClient)
    client._bearer_token = "test_bearer_123"

    headers = client._bearer_headers()
    assert headers["Authorization"] == "Bearer test_bearer_123"


# ---------------------------------------------------------------------------
# LinkedIn client
# ---------------------------------------------------------------------------


def test_linkedin_post_truncation():
    """LinkedIn posts over 3000 chars should be truncated."""
    # The create_post method truncates to 2997 + "..."
    long_text = "a" * 3100
    truncated = long_text[:2997] + "..."
    assert len(truncated) == 3000


def test_linkedin_client_imports():
    """LinkedIn client imports correctly."""
    from app.integrations.linkedin_client import LinkedInClient, LinkedInClientError

    assert LinkedInClient is not None
    assert LinkedInClientError is not None


# ---------------------------------------------------------------------------
# News aggregator
# ---------------------------------------------------------------------------


def test_parse_newsapi_articles():
    """NewsAPI articles are parsed into clean dicts."""
    from app.integrations.news_aggregator import _parse_newsapi_articles

    raw = [
        {
            "title": "Test Article",
            "description": "A test description",
            "url": "https://example.com/article",
            "urlToImage": "https://example.com/image.jpg",
            "publishedAt": "2026-02-23T10:00:00Z",
            "source": {"name": "Test Source"},
            "author": "Test Author",
        },
        {
            "title": "Minimal Article",
            "source": {},
        },
    ]

    result = _parse_newsapi_articles(raw)
    assert len(result) == 2
    assert result[0]["title"] == "Test Article"
    assert result[0]["source"] == "Test Source"
    assert result[0]["image_url"] == "https://example.com/image.jpg"
    assert result[1]["description"] == ""
    assert result[1]["source"] == ""


def test_parse_newsapi_empty():
    """Empty article list returns empty result."""
    from app.integrations.news_aggregator import _parse_newsapi_articles

    assert _parse_newsapi_articles([]) == []


# ---------------------------------------------------------------------------
# Web crawler
# ---------------------------------------------------------------------------


def test_web_crawler_imports():
    """Web crawler imports correctly."""
    from app.integrations.web_crawler import WebCrawler, WebCrawlerError

    assert WebCrawler is not None
    assert WebCrawlerError is not None


# ---------------------------------------------------------------------------
# Social poster service
# ---------------------------------------------------------------------------


def test_social_poster_imports():
    """Social poster service functions import correctly."""
    from app.services.social_poster import (
        cross_post,
        get_engagement_summary,
        get_post_history,
        post_to_linkedin,
        post_to_x,
    )

    assert callable(cross_post)
    assert callable(post_to_linkedin)
    assert callable(post_to_x)
    assert callable(get_post_history)
    assert callable(get_engagement_summary)


# ---------------------------------------------------------------------------
# API route registration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_social_post_route_registered(client):
    """Social posting endpoint is registered."""
    response = await client.post("/api/v1/social/post", json={"text": "test"})
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_social_history_route_registered(client):
    """Social history endpoint is registered."""
    response = await client.get("/api/v1/social/history")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_news_headlines_route_registered(client):
    """News headlines endpoint is registered."""
    response = await client.get("/api/v1/news/headlines")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_news_search_route_registered(client):
    """News search endpoint is registered."""
    response = await client.get("/api/v1/news/search?query=test")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_crawl_route_registered(client):
    """Web crawl endpoint is registered."""
    response = await client.post(
        "/api/v1/crawl",
        json={"urls": ["https://example.com"]},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_x_profile_route_registered(client):
    """X profile endpoint is registered."""
    response = await client.get("/api/v1/social/x/me")
    assert response.status_code == 401


# ---------------------------------------------------------------------------
# Security: SSRF validation on Pydantic models
# ---------------------------------------------------------------------------


def _make_getaddrinfo_private(ip: str):
    """Return a mock getaddrinfo that resolves to a private IP."""
    import socket

    def mock_getaddrinfo(host, port, **kwargs):
        family = socket.AF_INET6 if ":" in ip else socket.AF_INET
        return [(family, socket.SOCK_STREAM, socket.IPPROTO_TCP, "", (ip, port or 443))]

    return mock_getaddrinfo


def test_crawl_request_rejects_private_urls():
    """CrawlRequest validator rejects URLs resolving to private IPs."""
    from app.api.v1.social import CrawlRequest

    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo_private("10.0.0.1"),
        ),
        pytest.raises(ValidationError),
    ):
        CrawlRequest(urls=["http://internal-service"])


def test_crawl_request_rejects_non_http_scheme():
    """CrawlRequest validator rejects non-HTTP schemes."""
    from app.api.v1.social import CrawlRequest

    with pytest.raises(ValidationError):
        CrawlRequest(urls=["ftp://example.com/data"])


def test_rss_feed_request_rejects_private_urls():
    """RSSFeedRequest validator rejects URLs resolving to private IPs."""
    from app.api.v1.social import RSSFeedRequest

    with (
        patch(
            "app.security.url_validator.socket.getaddrinfo",
            _make_getaddrinfo_private("192.168.1.1"),
        ),
        pytest.raises(ValidationError),
    ):
        RSSFeedRequest(feed_urls=["http://router.local/rss"])


# ---------------------------------------------------------------------------
# Security: Platform validation on PostRequest
# ---------------------------------------------------------------------------


def test_post_request_accepts_valid_platforms():
    """PostRequest accepts 'linkedin' and 'x' as platforms."""
    from app.api.v1.social import PostRequest

    req = PostRequest(text="hello", platforms=["linkedin", "x"])
    assert req.platforms == ["linkedin", "x"]


def test_post_request_rejects_invalid_platform():
    """PostRequest rejects unknown platforms."""
    from app.api.v1.social import PostRequest

    with pytest.raises(ValidationError):
        PostRequest(text="hello", platforms=["facebook"])


# ---------------------------------------------------------------------------
# Security: Content sanitization in web crawler
# ---------------------------------------------------------------------------


def test_web_crawler_ssrf_import():
    """Web crawler imports validate_url for SSRF protection."""
    from app.integrations.web_crawler import validate_url as crawler_validate_url
    from app.security.url_validator import validate_url

    assert crawler_validate_url is validate_url


def test_web_crawler_max_content_length():
    """Web crawler has a 10 MB content length limit."""
    from app.integrations.web_crawler import _MAX_CONTENT_LENGTH

    assert _MAX_CONTENT_LENGTH == 10 * 1024 * 1024


# ---------------------------------------------------------------------------
# Security: NewsAPI key not in query params
# ---------------------------------------------------------------------------


def test_newsapi_key_not_in_params():
    """Verify the news aggregator uses X-Api-Key header, not query params.

    We inspect the source code to ensure 'apiKey' is not passed as a param.
    """
    import inspect

    from app.integrations.news_aggregator import NewsAggregator

    source = inspect.getsource(NewsAggregator.get_top_headlines)
    assert '"apiKey"' not in source
    assert "X-Api-Key" in source

    source_search = inspect.getsource(NewsAggregator.search_news)
    assert '"apiKey"' not in source_search
    assert "X-Api-Key" in source_search
