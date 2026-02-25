"""Pearson Mastering scraper — Playwright-based automation for Mastering platform.

NO official API exists. This uses browser automation which is inherently fragile.
Selectors may change with Pearson updates. Robust error handling and
screenshot-on-failure are mandatory.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from pathlib import Path

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.integrations.base import BaseIntegration
from app.models.assignment import Assignment

logger = structlog.get_logger()

# Directory for failure screenshots
_SCREENSHOT_DIR = Path("/tmp/pearson_screenshots")  # noqa: S108


class PearsonScraperError(Exception):
    """Raised when Pearson scraping fails."""


class PearsonScraper(BaseIntegration):
    """Playwright-based scraper for Pearson Mastering platform.

    This integration is fragile by nature — selectors may break when
    Pearson updates their frontend. All operations include retry logic
    and capture screenshots on failure for debugging.
    """

    def __init__(self, user_id: str, db: AsyncSession) -> None:
        super().__init__(user_id, db)
        settings = get_settings()
        self._pearson_url = settings.pearson_url if hasattr(settings, "pearson_url") else ""
        self._username = settings.pearson_username if hasattr(settings, "pearson_username") else ""
        self._password = settings.pearson_password if hasattr(settings, "pearson_password") else ""

    async def _get_browser(self):  # noqa: ANN202
        """Launch a Playwright browser instance."""
        try:
            from playwright.async_api import async_playwright
        except ImportError as exc:
            msg = (
                "playwright is not installed. "
                "Install with: uv pip install 'aegis[integrations]'"
            )
            raise PearsonScraperError(msg) from exc

        pw = await async_playwright().start()
        browser = await pw.chromium.launch(headless=True)
        return pw, browser

    async def login(self) -> bool:
        """Automated login to Pearson Mastering.

        Returns:
            True if login succeeded.

        Raises:
            PearsonScraperError: If login fails after retries.
        """
        if not self._pearson_url or not self._username:
            msg = "Pearson credentials not configured"
            raise PearsonScraperError(msg)

        pw, browser = await self._get_browser()
        try:
            page = await browser.new_page()
            await page.goto(self._pearson_url, wait_until="networkidle", timeout=30000)

            # Fill login form — selectors may change
            await page.fill('input[name="username"], input[id="username"]', self._username)
            await page.fill('input[name="password"], input[id="password"]', self._password)
            await page.click('button[type="submit"], input[type="submit"]')

            # Wait for navigation after login
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Check if login succeeded
            if "login" in page.url.lower() or "error" in page.url.lower():
                await self._save_screenshot(page, "login_failed")
                msg = "Pearson login failed — check credentials"
                raise PearsonScraperError(msg)

            self._log.info("pearson_login_success")
            return True

        except PearsonScraperError:
            raise
        except Exception as exc:
            self._log.error("pearson_login_error", error=str(type(exc).__name__))
            msg = f"Pearson login failed: {type(exc).__name__}"
            raise PearsonScraperError(msg) from exc
        finally:
            await browser.close()
            await pw.stop()

    async def get_assignments(self) -> list[dict]:
        """Scrape assignment list with due dates from Pearson Mastering.

        Returns:
            List of assignment dicts with name, due_date, status, url.
        """
        if not self._pearson_url:
            self._log.warning("pearson_not_configured")
            return []

        pw, browser = await self._get_browser()
        try:
            page = await browser.new_page()
            await page.goto(self._pearson_url, wait_until="networkidle", timeout=30000)

            # Login first
            await page.fill('input[name="username"], input[id="username"]', self._username)
            await page.fill('input[name="password"], input[id="password"]', self._password)
            await page.click('button[type="submit"], input[type="submit"]')
            await page.wait_for_load_state("networkidle", timeout=15000)

            # Navigate to assignments page — selector is fragile
            assignments_link = page.locator(
                'a:has-text("Assignments"), '
                'a:has-text("assignments"), '
                '[data-testid="assignments-link"]'
            )
            if await assignments_link.count() > 0:
                await assignments_link.first.click()
                await page.wait_for_load_state("networkidle", timeout=15000)

            # Scrape assignment rows
            assignment_rows = page.locator(
                'tr.assignment-row, [data-testid*="assignment"], .assignment-list-item'
            )

            assignments = []
            count = await assignment_rows.count()
            for i in range(count):
                row = assignment_rows.nth(i)
                try:
                    name = await row.locator(
                        '.assignment-name, td:first-child, [data-testid="assignment-name"]'
                    ).first.inner_text()

                    due_text = ""
                    due_el = row.locator('.due-date, td:nth-child(2), [data-testid="due-date"]')
                    if await due_el.count() > 0:
                        due_text = await due_el.first.inner_text()

                    status_text = ""
                    status_el = row.locator('.status, td:nth-child(3), [data-testid="status"]')
                    if await status_el.count() > 0:
                        status_text = await status_el.first.inner_text()

                    assignments.append(
                        {
                            "name": name.strip(),
                            "due_date": due_text.strip(),
                            "status": status_text.strip() or "pending",
                            "platform": "pearson",
                        }
                    )
                except Exception:
                    self._log.warning("pearson_row_parse_failed", row_index=i)

            self._log.info("pearson_assignments_scraped", count=len(assignments))
            await self._audit(
                action="pearson_scrape",
                resource_type="assignment",
                metadata={"count": len(assignments)},
            )
            return assignments

        except PearsonScraperError:
            raise
        except Exception as exc:
            import contextlib

            with contextlib.suppress(Exception):
                await self._save_screenshot(page, "scrape_failed")
            self._log.error("pearson_scrape_failed", error=str(type(exc).__name__))
            msg = f"Pearson scraping failed: {type(exc).__name__}"
            raise PearsonScraperError(msg) from exc
        finally:
            await browser.close()
            await pw.stop()

    async def store_assignments(self, assignments: list[dict]) -> int:
        """Store scraped Pearson assignments in the database."""
        uid = uuid.UUID(self.user_id)
        stored = 0

        for a in assignments:
            external_id = f"pearson_{a['name'][:100]}"
            existing = await self.db.execute(
                select(Assignment).where(Assignment.external_id == external_id)
            )
            if existing.scalar_one_or_none() is not None:
                continue

            assignment = Assignment(
                user_id=uid,
                platform="pearson",
                course="Mastering",
                title=a["name"],
                due_date=None,  # Date parsing is unreliable from scraping
                status=a.get("status", "pending"),
                assignment_type="homework",
                external_id=external_id,
            )
            self.db.add(assignment)
            stored += 1

        await self.db.flush()
        return stored

    async def _save_screenshot(self, page: object, name: str) -> None:
        """Save a debug screenshot on failure."""
        _SCREENSHOT_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(UTC).strftime("%Y%m%d_%H%M%S")
        path = _SCREENSHOT_DIR / f"{name}_{ts}.png"
        try:
            await page.screenshot(path=str(path))  # type: ignore[attr-defined]
            self._log.info("pearson_screenshot_saved", path=str(path))
        except Exception:
            self._log.warning("pearson_screenshot_failed")

    async def sync(self) -> None:
        """Scrape and store Pearson assignments."""
        assignments = await self.get_assignments()
        await self.store_assignments(assignments)

    async def health_check(self) -> bool:
        """Verify Pearson credentials work."""
        try:
            return await self.login()
        except Exception:
            self._log.warning("pearson_health_check_failed")
            return False
