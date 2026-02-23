"""Social media posting service — cross-platform content publishing."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.content import ContentPost
from app.security.audit import audit_log

logger = structlog.get_logger()


async def post_to_linkedin(
    db: AsyncSession,
    user_id: str,
    text: str,
    *,
    visibility: str = "PUBLIC",
) -> dict:
    """Post content to LinkedIn and store the result.

    Args:
        db: Database session.
        user_id: User identifier.
        text: Post content.
        visibility: PUBLIC, CONNECTIONS, or LOGGED_IN.

    Returns:
        Dict with post details and stored ID.
    """
    from app.integrations.linkedin_client import LinkedInClient

    client = LinkedInClient(user_id, db)
    result = await client.create_post(text, visibility=visibility)
    post_id = await client.store_post(result, text)

    logger.info("social_post_linkedin", user_id=user_id, post_id=post_id)
    return {**result, "stored_id": post_id}


async def post_to_x(
    db: AsyncSession,
    user_id: str,
    text: str,
) -> dict:
    """Post content to X (Twitter) and store the result.

    Args:
        db: Database session.
        user_id: User identifier.
        text: Tweet content.

    Returns:
        Dict with tweet details and stored ID.
    """
    from app.integrations.x_client import XClient

    client = XClient(user_id, db)
    result = await client.create_tweet(text)
    post_id = await client.store_tweet(result, text)

    logger.info("social_post_x", user_id=user_id, post_id=post_id)
    return {**result, "stored_id": post_id}


async def cross_post(
    db: AsyncSession,
    user_id: str,
    text: str,
    *,
    platforms: list[str] | None = None,
) -> dict:
    """Post content to multiple platforms simultaneously.

    Args:
        db: Database session.
        user_id: User identifier.
        text: Content to post.
        platforms: List of platforms to post to. Defaults to ["linkedin", "x"].

    Returns:
        Dict with results per platform.
    """
    if platforms is None:
        platforms = ["linkedin", "x"]

    results: dict = {}

    for platform in platforms:
        try:
            if platform == "linkedin":
                results["linkedin"] = await post_to_linkedin(db, user_id, text)
            elif platform == "x":
                results["x"] = await post_to_x(db, user_id, text)
            else:
                results[platform] = {"error": f"Unknown platform: {platform}"}
        except Exception as exc:
            logger.warning(
                "cross_post_failed",
                platform=platform,
                error=str(type(exc).__name__),
            )
            results[platform] = {"error": str(type(exc).__name__), "status": "failed"}

    uid = uuid.UUID(user_id)
    await audit_log(
        db,
        action="social_cross_post",
        resource_type="content",
        user_id=uid,
        metadata={
            "platforms": platforms,
            "success": [p for p in results if "error" not in results[p]],
        },
    )

    return results


async def get_post_history(
    db: AsyncSession,
    user_id: str,
    *,
    platform: str | None = None,
    limit: int = 50,
) -> list[dict]:
    """Get posting history for a user.

    Args:
        db: Database session.
        user_id: User identifier.
        platform: Filter by platform (linkedin, x, or None for all).
        limit: Max results.

    Returns:
        List of post dicts sorted by most recent first.
    """
    uid = uuid.UUID(user_id)
    query = select(ContentPost).where(ContentPost.user_id == uid)
    if platform:
        query = query.where(ContentPost.platform == platform)
    query = query.order_by(ContentPost.created_at.desc()).limit(limit)

    result = await db.execute(query)
    posts = result.scalars().all()

    return [
        {
            "id": str(p.id),
            "platform": p.platform,
            "content": p.content[:500],
            "status": p.status,
            "posted_at": p.posted_at.isoformat() if p.posted_at else None,
            "external_post_id": p.external_post_id,
            "engagement": p.engagement_metrics,
        }
        for p in posts
    ]


async def get_engagement_summary(
    db: AsyncSession,
    user_id: str,
) -> dict:
    """Summarize engagement metrics across all platforms.

    Returns:
        Dict with per-platform metrics and totals.
    """
    uid = uuid.UUID(user_id)
    result = await db.execute(
        select(ContentPost).where(
            ContentPost.user_id == uid,
            ContentPost.status == "published",
        )
    )
    posts = result.scalars().all()

    summary: dict = {
        "total_posts": len(posts),
        "platforms": {},
    }

    for post in posts:
        platform = post.platform
        if platform not in summary["platforms"]:
            summary["platforms"][platform] = {
                "count": 0,
                "total_engagement": 0,
            }

        summary["platforms"][platform]["count"] += 1
        if post.engagement_metrics:
            engagement = sum(
                v for v in post.engagement_metrics.values() if isinstance(v, int | float)
            )
            summary["platforms"][platform]["total_engagement"] += engagement

    return summary
