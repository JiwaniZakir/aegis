"""Meeting transcription and summarization service."""

from __future__ import annotations

import uuid
from datetime import datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import get_settings
from app.models.meeting import Meeting
from app.security.audit import audit_log
from app.security.encryption import encrypt_field

logger = structlog.get_logger()


async def transcribe(audio_path: str) -> str:
    """Transcribe an audio file to text.

    Tries Deepgram API first, falls back to a placeholder if unavailable.

    Args:
        audio_path: Path to the audio file.

    Returns:
        Full transcript text.
    """
    settings = get_settings()

    # Try Deepgram API
    if settings.deepgram_api_key:
        try:
            return await _transcribe_deepgram(audio_path, settings.deepgram_api_key)
        except Exception as exc:
            logger.warning(
                "deepgram_transcription_failed",
                error=str(type(exc).__name__),
            )

    # Fallback: return placeholder indicating manual transcription needed
    logger.warning("no_transcription_service_available")
    return "[Transcription service unavailable. Audio file saved for manual review.]"


async def _transcribe_deepgram(audio_path: str, api_key: str) -> str:
    """Transcribe using the Deepgram API."""
    import httpx

    with open(audio_path, "rb") as f:  # noqa: ASYNC230
        audio_data = f.read()

    async with httpx.AsyncClient(timeout=120) as client:
        response = await client.post(
            "https://api.deepgram.com/v1/listen",
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "audio/wav",
            },
            content=audio_data,
            params={
                "model": "nova-2",
                "smart_format": "true",
                "punctuate": "true",
                "paragraphs": "true",
            },
        )
        response.raise_for_status()
        data = response.json()

    channels = data.get("results", {}).get("channels", [])
    if channels:
        alternatives = channels[0].get("alternatives", [])
        if alternatives:
            return alternatives[0].get("transcript", "")

    return ""


async def summarize_meeting(
    db: AsyncSession,
    user_id: str,
    transcript: str,
    meeting_title: str = "",
) -> dict:
    """Generate an LLM-powered meeting summary.

    Returns:
        dict with key_points, action_items, follow_ups, decisions.
    """
    settings = get_settings()

    summary = {
        "key_points": [],
        "action_items": [],
        "follow_ups": [],
        "decisions": [],
        "summary_text": "",
    }

    if settings.anthropic_api_key and transcript:
        try:
            import anthropic

            client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
            message = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1000,
                messages=[
                    {
                        "role": "user",
                        "content": (
                            f"Summarize this meeting transcript. "
                            f"Title: {meeting_title}\n\n"
                            f"Transcript:\n{transcript[:10000]}\n\n"
                            f"Provide:\n"
                            f"1. A brief summary (2-3 sentences)\n"
                            f"2. Key points (bullet list)\n"
                            f"3. Action items with owners\n"
                            f"4. Follow-ups needed\n"
                            f"5. Decisions made\n\n"
                            f"Format as JSON with keys: summary_text, key_points, "
                            f"action_items, follow_ups, decisions"
                        ),
                    }
                ],
            )
            import json

            try:
                text = message.content[0].text
                # Try to parse JSON from the response
                if "{" in text:
                    json_start = text.index("{")
                    json_end = text.rindex("}") + 1
                    parsed = json.loads(text[json_start:json_end])
                    summary.update(parsed)
            except (json.JSONDecodeError, ValueError):
                summary["summary_text"] = message.content[0].text

        except Exception as exc:
            logger.warning(
                "meeting_summarize_llm_failed",
                error=str(type(exc).__name__),
            )
            summary["summary_text"] = (
                "AI summarization unavailable. Transcript stored for manual review."
            )

    uid = uuid.UUID(user_id)
    await audit_log(
        db,
        action="meeting_summarize",
        resource_type="meeting",
        user_id=uid,
        metadata={"title": meeting_title},
    )

    logger.info("meeting_summarized", user_id=user_id, title=meeting_title)
    return summary


async def store_meeting(
    db: AsyncSession,
    user_id: str,
    title: str,
    start_time: datetime,
    transcript: str,
    summary: dict,
    *,
    end_time: datetime | None = None,
    attendees: list[dict] | None = None,
    source: str = "upload",
) -> str:
    """Store a meeting with encrypted transcript.

    Returns:
        Meeting ID as string.
    """
    settings = get_settings()
    uid = uuid.UUID(user_id)

    # Encrypt the transcript
    encrypted_transcript = None
    if transcript:
        encrypted_transcript = encrypt_field(
            transcript,
            settings.master_key_bytes,
            context=f"meeting.transcript.{user_id}",
        )

    meeting = Meeting(
        user_id=uid,
        title=title,
        start_time=start_time,
        end_time=end_time,
        attendees=attendees,
        encrypted_transcript=encrypted_transcript,
        summary=summary.get("summary_text", ""),
        action_items=summary.get("action_items"),
        source=source,
    )
    db.add(meeting)
    await db.flush()

    await audit_log(
        db,
        action="meeting_store",
        resource_type="meeting",
        resource_id=str(meeting.id),
        user_id=uid,
    )

    logger.info("meeting_stored", meeting_id=str(meeting.id))
    return str(meeting.id)
