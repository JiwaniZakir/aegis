"""Calendar sync Celery task — pulls latest events from all calendar sources."""

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
def sync_calendars(self: object) -> dict:
    """Sync calendar events from Google Calendar and Outlook for all configured users.

    Runs every 15 minutes via Celery Beat.
    """
    return asyncio.run(_sync_calendars_async(self))


async def _sync_calendars_async(task: object) -> dict:
    """Async implementation of calendar sync."""
    results: dict = {"google": 0, "outlook": 0, "errors": []}

    async with async_session_factory() as db:
        # Find users with Google Calendar credentials
        gcal_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "google_refresh_token").distinct()
        )
        for (user_id,) in gcal_users:
            try:
                from app.integrations.google_calendar_client import GoogleCalendarClient

                client = GoogleCalendarClient(str(user_id), db)
                await client.sync()
                results["google"] += 1
            except Exception as exc:
                logger.warning(
                    "gcal_sync_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"gcal:{user_id}:{type(exc).__name__}")

        # Find users with Outlook credentials
        outlook_users = await db.execute(
            select(Credential.user_id).where(Credential.key == "outlook_refresh_token").distinct()
        )
        for (user_id,) in outlook_users:
            try:
                from app.integrations.outlook_client import OutlookClient

                client = OutlookClient(str(user_id), db)
                await client.sync()
                results["outlook"] += 1
            except Exception as exc:
                logger.warning(
                    "outlook_sync_failed",
                    user_id=str(user_id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"outlook:{user_id}:{type(exc).__name__}")

        await db.commit()

    logger.info(
        "calendar_sync_complete",
        google=results["google"],
        outlook=results["outlook"],
        errors=len(results["errors"]),
    )
    return results
