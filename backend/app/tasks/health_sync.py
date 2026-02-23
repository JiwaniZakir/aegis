"""Health sync Celery task — processes health data from Garmin and Apple Health."""

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
    default_retry_delay=60,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_health(self: object) -> dict:
    """Sync health data from Garmin Connect for all configured users.

    Runs every hour via Celery Beat.
    Apple Health data is ingested via the API endpoint (push from device).
    """
    return asyncio.run(_sync_health_async(self))


async def _sync_health_async(task: object) -> dict:
    """Async implementation of health sync."""
    results: dict = {"garmin": 0, "errors": []}

    async with async_session_factory() as db:
        # Find users with Garmin credentials
        garmin_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "garmin_email").distinct()
        )
        for (user_id,) in garmin_users:
            try:
                from app.integrations.garmin_client import GarminClient

                client = GarminClient(str(user_id), db)
                await client.sync()
                results["garmin"] += 1
            except Exception as exc:
                logger.warning(
                    "garmin_sync_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"garmin:{user_id}:{type(exc).__name__}")

        await db.commit()

    logger.info(
        "health_sync_complete",
        garmin=results["garmin"],
        errors=len(results["errors"]),
    )
    return results
