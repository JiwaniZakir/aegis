"""Celery task for syncing health data from Garmin Connect."""

from __future__ import annotations

import asyncio

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.garmin_sync.sync_garmin",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_garmin(self: object) -> dict:
    """Sync health metrics from Garmin Connect for all configured users.

    Pulls steps, heart rate, sleep, and activity data via the unofficial
    ``garminconnect`` library.  Can be invoked independently of the broader
    ``health_sync`` task for on-demand refreshes.
    """
    logger.info("garmin_sync_started")

    try:
        result = asyncio.run(_sync_garmin_async())
        logger.info("garmin_sync_completed", result=result)
        return result
    except Exception as exc:
        logger.error("garmin_sync_failed", error=str(type(exc).__name__))
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


async def _sync_garmin_async() -> dict:
    """Fetch latest data from Garmin and store as health metrics."""
    from sqlalchemy import select

    from app.database import async_session_factory
    from app.models.credential import Credential

    results: dict = {"synced_users": 0, "errors": []}

    async with async_session_factory() as db:
        # Find users that have Garmin credentials configured
        garmin_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "garmin_email").distinct()
        )

        for (user_id,) in garmin_users:
            try:
                from app.integrations.garmin_client import GarminClient

                client = GarminClient(str(user_id), db)

                if not await client.health_check():
                    logger.warning("garmin_unavailable", user_id=str(user_id))
                    results["errors"].append(f"{user_id}:health_check_failed")
                    continue

                await client.sync()
                results["synced_users"] += 1
            except Exception as exc:
                logger.warning(
                    "garmin_sync_user_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"{user_id}:{type(exc).__name__}")

        await db.commit()

    logger.info(
        "garmin_sync_complete",
        synced_users=results["synced_users"],
        errors=len(results["errors"]),
    )
    return results
