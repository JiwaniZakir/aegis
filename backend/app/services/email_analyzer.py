"""Email analysis service — categorization, digests, and spam detection."""

from __future__ import annotations

import uuid
from datetime import UTC, date, datetime, timedelta

import structlog
from sqlalchemy import and_, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.email_digest import EmailDigest
from app.security.audit import audit_log

logger = structlog.get_logger()

# Email categories
CATEGORIES = ("priority", "informational", "promotional", "junk", "academic")


async def categorize_email(
    db: AsyncSession,
    user_id: str,
    email_data: dict,
) -> str:
    """Classify an email into one of 5 categories using Claude API.

    Categories: priority, informational, promotional, junk, academic.

    Falls back to heuristic classification when Claude API is unavailable.
    """
    settings = get_settings()

    subject = email_data.get("subject", "")
    sender = email_data.get("sender", "")
    snippet = email_data.get("snippet", "")

    # Try LLM classification first
    if settings.anthropic_api_key:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=20,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Classify this email into exactly one category: "
                            f"priority, informational, promotional, junk, academic.\n\n"
                            f"Subject: {subject}\n"
                            f"From: {sender}\n"
                            f"Preview: {snippet[:200]}\n\n"
                            f"Reply with only the category name."
                        ),
                    }
                ],
            )
            category = message.content[0].text.strip().lower()
            if category in CATEGORIES:
                return category
        except Exception as exc:
            logger.warning("email_categorize_llm_failed", error=str(type(exc).__name__))

    # Heuristic fallback
    return _heuristic_categorize(subject, sender, snippet)


def _heuristic_categorize(subject: str, sender: str, snippet: str) -> str:
    """Simple rule-based email classification."""
    lower_subject = subject.lower()
    lower_sender = sender.lower()

    # Academic indicators
    academic_keywords = ["assignment", "grade", "canvas", "blackboard", "due", "exam", "quiz"]
    if any(kw in lower_subject or kw in lower_sender for kw in academic_keywords):
        return "academic"

    # Priority indicators
    priority_keywords = ["urgent", "important", "action required", "deadline"]
    if any(kw in lower_subject for kw in priority_keywords):
        return "priority"

    # Promotional indicators
    promo_keywords = ["unsubscribe", "sale", "deal", "offer", "promo", "discount"]
    if any(kw in lower_subject or kw in snippet.lower() for kw in promo_keywords):
        return "promotional"

    # Junk indicators
    junk_keywords = ["noreply", "no-reply", "donotreply", "newsletter"]
    if any(kw in lower_sender for kw in junk_keywords):
        return "junk"

    return "informational"


async def daily_email_digest(db: AsyncSession, user_id: str) -> dict:
    """Generate a summarized digest of today's emails by priority.

    Returns:
        dict with categorized email summaries and counts.
    """
    uid = uuid.UUID(user_id)
    today_start = datetime.combine(date.today(), datetime.min.time(), tzinfo=UTC)

    result = await db.execute(
        select(EmailDigest)
        .where(
            and_(
                EmailDigest.user_id == uid,
                EmailDigest.email_date >= today_start,
            )
        )
        .order_by(EmailDigest.email_date.desc())
    )
    emails = result.scalars().all()

    categorized: dict[str, list[dict]] = {cat: [] for cat in CATEGORIES}
    for email in emails:
        cat = email.category or "informational"
        if cat not in categorized:
            cat = "informational"
        categorized[cat].append(
            {
                "subject": email.subject,
                "sender": email.sender,
                "date": str(email.email_date),
            }
        )

    digest = {
        "date": str(date.today()),
        "total_emails": len(emails),
        "by_category": {
            cat: {"count": len(items), "emails": items} for cat, items in categorized.items()
        },
    }

    await audit_log(
        db,
        action="daily_email_digest",
        resource_type="email",
        user_id=uid,
        metadata={"email_count": len(emails)},
    )

    logger.info("daily_email_digest_generated", user_id=user_id, count=len(emails))
    return digest


async def weekly_email_digest(db: AsyncSession, user_id: str) -> dict:
    """Generate a weekly productivity report analyzing email patterns.

    Returns:
        dict with weekly statistics, top senders, and recommendations.
    """
    uid = uuid.UUID(user_id)
    week_start = datetime.combine(
        date.today() - timedelta(days=7),
        datetime.min.time(),
        tzinfo=UTC,
    )

    result = await db.execute(
        select(EmailDigest)
        .where(
            and_(
                EmailDigest.user_id == uid,
                EmailDigest.email_date >= week_start,
            )
        )
        .order_by(EmailDigest.email_date.desc())
    )
    emails = result.scalars().all()

    # Aggregate stats
    from collections import Counter

    category_counts = Counter(e.category for e in emails)
    sender_counts = Counter(e.sender for e in emails)
    top_senders = sender_counts.most_common(10)

    digest = {
        "period": f"{str(date.today() - timedelta(days=7))} to {str(date.today())}",
        "total_emails": len(emails),
        "by_category": dict(category_counts),
        "top_senders": [{"sender": s, "count": c} for s, c in top_senders],
        "daily_average": round(len(emails) / 7, 1),
    }

    await audit_log(
        db,
        action="weekly_email_digest",
        resource_type="email",
        user_id=uid,
        metadata={"email_count": len(emails)},
    )

    logger.info("weekly_email_digest_generated", user_id=user_id, count=len(emails))
    return digest


async def spam_audit(db: AsyncSession, user_id: str) -> list[dict]:
    """Identify subscriptions/spam to unsubscribe from.

    Analyses email patterns to find frequent promotional/junk senders.

    Returns:
        List of senders recommended for unsubscription.
    """
    uid = uuid.UUID(user_id)
    cutoff = datetime.combine(
        date.today() - timedelta(days=30),
        datetime.min.time(),
        tzinfo=UTC,
    )

    result = await db.execute(
        select(
            EmailDigest.sender,
            EmailDigest.category,
            func.count(EmailDigest.id).label("count"),
        )
        .where(
            and_(
                EmailDigest.user_id == uid,
                EmailDigest.email_date >= cutoff,
                EmailDigest.category.in_(["promotional", "junk"]),
            )
        )
        .group_by(EmailDigest.sender, EmailDigest.category)
        .order_by(func.count(EmailDigest.id).desc())
    )

    recommendations = []
    for row in result:
        recommendations.append(
            {
                "sender": row.sender,
                "category": row.category,
                "email_count_30d": row.count,
                "recommendation": "unsubscribe",
            }
        )

    logger.info("spam_audit_complete", user_id=user_id, count=len(recommendations))
    return recommendations
