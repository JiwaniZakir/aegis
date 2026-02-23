"""Content generation Celery task — daily auto-posting to LinkedIn and X."""

from __future__ import annotations

import asyncio

import structlog
from sqlalchemy import select

from app.celery_app import celery_app
from app.database import async_session_factory
from app.models.credential import Credential

logger = structlog.get_logger()

# Default topics for daily content rotation
_DEFAULT_TOPICS = [
    "AI and machine learning trends",
    "software engineering best practices",
    "technology leadership insights",
    "data-driven decision making",
    "personal productivity and growth",
    "innovation in tech industry",
    "career development in engineering",
]


@celery_app.task(
    bind=True,
    max_retries=2,
    default_retry_delay=300,
    acks_late=True,
    reject_on_worker_lost=True,
)
def generate_daily_content(self: object) -> dict:
    """Generate and publish daily thought leadership posts.

    Runs daily at 7:00 AM via Celery Beat.
    Generates posts for LinkedIn and X, stores as drafts,
    then publishes (or queues for approval based on settings).
    """
    return asyncio.run(_generate_daily_content_async(self))


async def _generate_daily_content_async(task: object) -> dict:
    """Async implementation of daily content generation."""
    from datetime import UTC, date, datetime

    results: dict = {
        "date": str(date.today()),
        "generated": [],
        "published": [],
        "errors": [],
    }

    async with async_session_factory() as db:
        # Find users with content posting configured
        users = await db.execute(
            select(Credential.user_id)
            .where(
                Credential.key.in_(
                    [
                        "linkedin_access_token",
                        "x_bearer_token",
                    ]
                )
            )
            .distinct()
        )

        for (user_id,) in users:
            user_id_str = str(user_id)
            # Pick today's topic based on day of year
            day_index = datetime.now(UTC).timetuple().tm_yday
            topic = _DEFAULT_TOPICS[day_index % len(_DEFAULT_TOPICS)]

            # Generate LinkedIn post
            try:
                from app.services.content_engine import generate_post

                li_post = await generate_post(
                    db,
                    user_id_str,
                    topic=topic,
                    platform="linkedin",
                    tone="thought_leader",
                )
                results["generated"].append(
                    {
                        "platform": "linkedin",
                        "post_id": li_post["id"],
                    }
                )
            except Exception as exc:
                logger.warning(
                    "daily_linkedin_gen_failed",
                    user_id=user_id_str,
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"linkedin:{user_id}:{type(exc).__name__}")

            # Generate X post
            try:
                from app.services.content_engine import generate_post

                x_post = await generate_post(
                    db,
                    user_id_str,
                    topic=topic,
                    platform="x",
                    tone="casual",
                )
                results["generated"].append(
                    {
                        "platform": "x",
                        "post_id": x_post["id"],
                    }
                )
            except Exception as exc:
                logger.warning(
                    "daily_x_gen_failed",
                    user_id=user_id_str,
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"x:{user_id}:{type(exc).__name__}")

        await db.commit()

    logger.info(
        "daily_content_generation_complete",
        generated=len(results["generated"]),
        errors=len(results["errors"]),
    )
    return results
