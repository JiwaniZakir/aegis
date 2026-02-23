"""Social media sync Celery task — pulls engagement and feed data."""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import async_session_factory
from app.models.credential import Credential

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_social(self: object) -> dict:
    """Sync social media data from LinkedIn and X for all configured users.

    Runs every 2 hours via Celery Beat.
    """
    return asyncio.run(_sync_social_async(self))


async def _sync_social_async(task: object) -> dict:
    """Async implementation of social media sync."""
    results: dict = {"linkedin": 0, "x": 0, "news": 0, "errors": []}

    async with async_session_factory() as db:
        # Find users with LinkedIn credentials
        li_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "linkedin_access_token").distinct()
        )
        for (user_id,) in li_users:
            try:
                from app.integrations.linkedin_client import LinkedInClient

                client = LinkedInClient(str(user_id), db)
                await client.sync()
                results["linkedin"] += 1
            except Exception as exc:
                logger.warning(
                    "linkedin_sync_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"linkedin:{user_id}:{type(exc).__name__}")

        # Find users with X credentials
        x_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "x_bearer_token").distinct()
        )
        for (user_id,) in x_users:
            try:
                from app.integrations.x_client import XClient

                client = XClient(str(user_id), db)
                await client.sync()
                results["x"] += 1
            except Exception as exc:
                logger.warning(
                    "x_sync_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"x:{user_id}:{type(exc).__name__}")

        # News aggregation (system-level, not per-user)
        try:
            from app.integrations.news_aggregator import NewsAggregator

            # Use first available user for audit logging
            first_user = await db.execute(select(Credential.user_id).limit(1))
            row = first_user.first()
            if row:
                news = NewsAggregator(str(row[0]), db)
                await news.sync()
                results["news"] += 1
        except Exception as exc:
            logger.warning("news_sync_failed", error=str(type(exc).__name__))
            results["errors"].append(f"news:{type(exc).__name__}")

        await db.commit()

    logger.info(
        "social_sync_complete",
        linkedin=results["linkedin"],
        x=results["x"],
        news=results["news"],
        errors=len(results["errors"]),
    )
    return results
