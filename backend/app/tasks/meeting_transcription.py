"""Celery task for transcribing and summarizing meeting recordings."""

from __future__ import annotations

import asyncio

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.meeting_transcription.transcribe_meetings",
    max_retries=2,
    default_retry_delay=300,  # 5 min delay — transcription is expensive
    acks_late=True,
    reject_on_worker_lost=True,
)
def transcribe_meetings(self: object) -> dict:
    """Find meetings without summaries and generate them.

    Meetings may have encrypted transcripts (from audio uploads) but lack
    AI-generated summaries and action items.  This task fills in that gap.

    Can also be invoked on-demand after a batch of meeting uploads.
    """
    logger.info("meeting_transcription_started")

    try:
        result = asyncio.run(_transcribe_async())
        logger.info("meeting_transcription_completed", result=result)
        return result
    except Exception as exc:
        logger.error("meeting_transcription_failed", error=str(type(exc).__name__))
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


async def _transcribe_async() -> dict:
    """Find meetings missing summaries and process them."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.database import async_session_factory
    from app.models.meeting import Meeting
    from app.security.encryption import decrypt_field

    settings = get_settings()

    results: dict = {"summarized": 0, "skipped": 0, "errors": []}

    async with async_session_factory() as db:
        # Find meetings that have an encrypted transcript but no summary yet.
        # These are meetings whose audio was processed but the LLM summary
        # step was either skipped or failed on first attempt.
        stmt = (
            select(Meeting)
            .where(
                Meeting.encrypted_transcript.isnot(None),
                Meeting.summary.is_(None),
            )
            .limit(5)  # Process at most 5 per run to bound LLM costs
        )
        result = await db.execute(stmt)
        meetings = result.scalars().all()

        if not meetings:
            logger.info("meeting_transcription_nothing_to_do")
            return {"summarized": 0, "skipped": 0, "errors": []}

        for meeting in meetings:
            try:
                # Decrypt the transcript so we can summarize it
                transcript = decrypt_field(
                    meeting.encrypted_transcript,
                    settings.master_key_bytes,
                    context=f"meeting.transcript.{meeting.user_id}",
                )

                if not transcript or transcript.startswith("[Transcription service"):
                    results["skipped"] += 1
                    continue

                from app.services.meeting_transcriber import summarize_meeting

                summary = await summarize_meeting(
                    db,
                    str(meeting.user_id),
                    transcript,
                    meeting_title=meeting.title,
                )

                # Update the meeting record with the generated summary
                meeting.summary = summary.get("summary_text", "")
                meeting.action_items = summary.get("action_items")

                results["summarized"] += 1
                logger.info(
                    "meeting_summarized",
                    meeting_id=str(meeting.id),
                    title=meeting.title,
                )
            except Exception as exc:
                logger.warning(
                    "meeting_transcription_single_failed",
                    meeting_id=str(meeting.id),
                    error=str(type(exc).__name__),
                )
                results["errors"].append(f"{meeting.id}:{type(exc).__name__}")

        await db.commit()

    return results
