"""Web crawler — Playwright + BeautifulSoup for content discovery and extraction."""

from __future__ import annotations

import html
from datetime import UTC, datetime

import httpx
import structlog
from sqlalchemy.ext.asyncio import AsyncSession
from tenacity import retry, retry_if_exception_type, stop_after_attempt, wait_exponential

from app.integrations.base import BaseIntegration
from app.security.url_validator import validate_url

logger = structlog.get_logger()

# Maximum response body size: 10 MB.
_MAX_CONTENT_LENGTH = 10 * 1024 * 1024


class WebCrawlerError(Exception):
    """Raised when web crawling fails."""


class WebCrawler(BaseIntegration):
    """Web content crawler for news, events, and research.

    Uses httpx for simple fetches and Playwright for JavaScript-rendered pages.
    BeautifulSoup for HTML parsing.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)

    @retry(
        stop=stop_after_attempt(3),
        wait=wait_exponential(multiplier=1, min=2, max=10),
        retry=retry_if_exception_type((httpx.ConnectError, httpx.TimeoutException)),
        reraise=True,
    )
    async def fetch_page(self, url: str, *, use_browser: bool = False) -> dict:
        """Fetch a web page and extract structured content.

        Args:
            url: URL to fetch.
            use_browser: Use Playwright for JS-rendered pages.

        Returns:
            Dict with title, text, links, meta.

        Raises:
            SSRFError: If the URL targets a private/internal network resource.
        """
        validate_url(url)

        if use_browser:
            return await self._fetch_with_playwright(url)
        return await self._fetch_with_httpx(url)

    async def _fetch_with_httpx(self, url: str) -> dict:
        """Fetch page with httpx and parse with BeautifulSoup."""
        try:
            from bs4 import BeautifulSoup
        except ImportError as exc:
            msg = "beautifulsoup4 is required. Install with: uv add beautifulsoup4"
            raise WebCrawlerError(msg) from exc

        async with httpx.AsyncClient(
            timeout=30,
            follow_redirects=True,
            headers={"User-Agent": "ClawdBot/1.0 (Personal Research Assistant)"},
        ) as client:
            response = await client.get(url)
            response.raise_for_status()

        # Enforce response size limit (10 MB)
        content_length = len(response.content)
        if content_length > _MAX_CONTENT_LENGTH:
            msg = (
                f"Response body too large ({content_length} bytes); "
                f"limit is {_MAX_CONTENT_LENGTH} bytes"
            )
            raise WebCrawlerError(msg)

        soup = BeautifulSoup(response.text, "html.parser")

        # Remove script and style elements
        for element in soup(["script", "style", "nav", "footer", "header"]):
            element.decompose()

        raw_title = soup.title.string.strip() if soup.title and soup.title.string else ""
        title = html.escape(raw_title)

        # Extract main text content
        text = soup.get_text(separator="\n", strip=True)
        # Collapse excessive whitespace
        lines = [line.strip() for line in text.splitlines() if line.strip()]
        clean_text = html.escape("\n".join(lines))

        # Extract links
        links = []
        for a_tag in soup.find_all("a", href=True)[:50]:
            href = a_tag["href"]
            if href.startswith(("http://", "https://")):
                links.append(
                    {
                        "url": href,
                        "text": html.escape(a_tag.get_text(strip=True)[:200]),
                    }
                )

        # Extract meta info
        meta = {}
        for tag in soup.find_all("meta"):
            name = tag.get("name", tag.get("property", ""))
            content = tag.get("content", "")
            if name and content:
                meta[html.escape(name)] = html.escape(content[:500])

        self._log.info("page_crawled", url=url, text_length=len(clean_text))
        await self._audit(
            action="web_crawl",
            resource_type="web_page",
            metadata={"url": url, "title": title[:200]},
        )

        return {
            "url": url,
            "title": title,
            "text": clean_text[:50000],
            "links": links,
            "meta": meta,
            "fetched_at": datetime.now(UTC).isoformat(),
        }

    async def _fetch_with_playwright(self, url: str) -> dict:
        """Fetch JS-rendered page with Playwright."""
        try:
            from bs4 import BeautifulSoup
            from playwright.async_api import async_playwright
        except ImportError as exc:
            msg = "playwright and beautifulsoup4 are required for browser crawling"
            raise WebCrawlerError(msg) from exc

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        try:
            page = await browser.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30000)
            html_content = await page.content()
            title = await page.title()

            soup = BeautifulSoup(html_content, "html.parser")
            for element in soup(["script", "style", "nav", "footer", "header"]):
                element.decompose()

            text = soup.get_text(separator="\n", strip=True)
            lines = [line.strip() for line in text.splitlines() if line.strip()]
            clean_text = html.escape("\n".join(lines))

            title = html.escape(title)

            links = []
            for a_tag in soup.find_all("a", href=True)[:50]:
                href = a_tag["href"]
                if href.startswith(("http://", "https://")):
                    links.append(
                        {
                            "url": href,
                            "text": html.escape(a_tag.get_text(strip=True)[:200]),
                        }
                    )

            self._log.info("page_crawled_browser", url=url, text_length=len(clean_text))
            await self._audit(
                action="web_crawl_browser",
                resource_type="web_page",
                metadata={"url": url, "title": title[:200]},
            )

            return {
                "url": url,
                "title": title,
                "text": clean_text[:50000],
                "links": links,
                "meta": {},
                "fetched_at": datetime.now(UTC).isoformat(),
            }
        finally:
            await browser.close()
            await pw.stop()

    async def crawl_multiple(self, urls: list[str]) -> list[dict]:
        """Crawl multiple URLs, collecting results and skipping failures."""
        results = []
        for url in urls:
            try:
                result = await self.fetch_page(url)
                results.append(result)
            except Exception as exc:
                self._log.warning("crawl_url_failed", url=url, error=str(type(exc).__name__))
                results.append(
                    {
                        "url": url,
                        "error": str(type(exc).__name__),
                        "fetched_at": datetime.now(UTC).isoformat(),
                    }
                )
        return results

    async def sync(self) -> None:
        """No-op for web crawler — crawling is on-demand."""

    async def health_check(self) -> bool:
        """Verify httpx can make requests."""
        try:
            async with httpx.AsyncClient(timeout=10) as client:
                response = await client.get("https://httpbin.org/status/200")
                return response.status_code == 200
        except Exception:
            self._log.warning("web_crawler_health_check_failed")
            return False
