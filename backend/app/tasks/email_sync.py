"""Celery task — periodic email and LMS synchronization."""

from __future__ import annotations

import asyncio

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.email_sync.sync_emails",
    max_retries=3,
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_emails(self: object) -> dict:
    """Synchronize emails from Gmail and assignments from LMS platforms.

    Runs every 30 minutes via Celery Beat.
    """
    logger.info("email_sync_started")

    try:
        result = asyncio.run(_sync_all_emails())
        logger.info("email_sync_completed", result=result)
        return result
    except Exception as exc:
        logger.error("email_sync_failed", error=str(type(exc).__name__))
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


async def _sync_all_emails() -> dict:
    """Async implementation of the email/LMS sync task."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.user import User

    results: dict = {
        "gmail": "skipped",
        "canvas": "skipped",
        "blackboard": "skipped",
        "pearson": "skipped",
    }

    async with async_session_factory() as db:
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if user is None:
            logger.warning("email_sync_no_user")
            return results

        user_id = str(user.id)

        # Sync Gmail
        try:
            from app.integrations.gmail_client import GmailClient

            gmail = GmailClient(user_id, db)
            await gmail.sync()
            results["gmail"] = "success"
        except KeyError:
            logger.info("email_sync_gmail_no_credentials")
            results["gmail"] = "no_credentials"
        except Exception as exc:
            logger.error("email_sync_gmail_error", error=str(type(exc).__name__))
            results["gmail"] = f"error: {type(exc).__name__}"

        # Sync Canvas
        try:
            from app.integrations.canvas_client import CanvasClient

            canvas = CanvasClient(user_id, db)
            await canvas.sync()
            results["canvas"] = "success"
        except Exception as exc:
            logger.error("email_sync_canvas_error", error=str(type(exc).__name__))
            results["canvas"] = f"error: {type(exc).__name__}"

        # Sync Blackboard
        try:
            from app.integrations.blackboard_client import BlackboardClient

            bb = BlackboardClient(user_id, db)
            await bb.sync()
            results["blackboard"] = "success"
        except Exception as exc:
            logger.error("email_sync_blackboard_error", error=str(type(exc).__name__))
            results["blackboard"] = f"error: {type(exc).__name__}"

        # Sync Pearson (fragile — don't fail the entire task)
        try:
            from app.integrations.pearson_scraper import PearsonScraper, PearsonScraperError

            scraper = PearsonScraper(user_id, db)
            await scraper.sync()
            results["pearson"] = "success"
        except PearsonScraperError as exc:
            logger.warning("email_sync_pearson_scraper_error", error=str(exc))
            results["pearson"] = f"scraper_error: {exc}"
        except Exception as exc:
            logger.error("email_sync_pearson_error", error=str(type(exc).__name__))
            results["pearson"] = f"error: {type(exc).__name__}"

        await db.commit()

    return results
