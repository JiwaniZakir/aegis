"""Celery task — periodic WhatsApp message synchronization via bridge sidecar."""

from __future__ import annotations

import asyncio

import structlog

from app.celery_app import celery_app

logger = structlog.get_logger()


@celery_app.task(
    bind=True,
    name="app.tasks.whatsapp_sync.sync_whatsapp",
    max_retries=3,
    default_retry_delay=120,
    acks_late=True,
    reject_on_worker_lost=True,
)
def sync_whatsapp(self: object) -> dict:
    """Sync recent WhatsApp messages from the bridge sidecar.

    Runs periodically via Celery Beat. Pulls messages from the
    whatsapp-web.js bridge, encrypts message bodies, and stores
    them in the database.
    """
    logger.info("whatsapp_sync_started")

    try:
        result = asyncio.run(_sync_whatsapp_async())
        logger.info("whatsapp_sync_completed", result=result)
        return result
    except Exception as exc:
        logger.error("whatsapp_sync_failed", error=str(type(exc).__name__))
        raise self.retry(exc=exc) from exc  # type: ignore[attr-defined]


async def _sync_whatsapp_async() -> dict:
    """Async implementation of the WhatsApp sync task."""
    from sqlalchemy import select

    from app.config import get_settings
    from app.database import async_session_factory
    from app.integrations.whatsapp_bridge import WhatsAppBridgeClient, WhatsAppBridgeError
    from app.models.user import User
    from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
    from app.security.encryption import encrypt_field

    async with async_session_factory() as db:
        # Look up the single admin user
        user_result = await db.execute(select(User).limit(1))
        user = user_result.scalar_one_or_none()
        if user is None:
            logger.warning("whatsapp_sync_no_user")
            return {"status": "skipped", "reason": "no_user"}

        user_id = str(user.id)
        client = WhatsAppBridgeClient(user_id, db)

        # Check bridge availability before attempting sync
        if not await client.health_check():
            logger.warning("whatsapp_bridge_unavailable")
            return {"status": "skipped", "reason": "bridge_unavailable"}

        try:
            messages = await client.get_recent_messages(limit=100)
        except WhatsAppBridgeError as exc:
            logger.error("whatsapp_fetch_failed", error=str(exc))
            return {"status": "error", "detail": str(exc)}

        settings = get_settings()
        stored = 0

        for msg in messages:
            phone = msg.get("phone", "unknown")
            sender = msg.get("sender", "unknown")
            body = msg.get("body", "")

            # Find or create conversation
            result = await db.execute(
                select(WhatsAppConversation).where(
                    WhatsAppConversation.contact_phone == phone,
                    WhatsAppConversation.user_id == user.id,
                )
            )
            conversation = result.scalar_one_or_none()

            if conversation is None:
                conversation = WhatsAppConversation(
                    user_id=user.id,
                    contact_name=msg.get("contact_name", phone),
                    contact_phone=phone,
                    is_group=msg.get("is_group", False),
                )
                db.add(conversation)
                await db.flush()

            # Encrypt the full message body for at-rest protection
            context = f"whatsapp:message:{conversation.id}"
            encrypted = encrypt_field(body, settings.master_key_bytes, context=context)

            # Store truncated preview in body, full encrypted in encrypted_body
            preview = (body[:100] + "...") if len(body) > 100 else body  # noqa: PLR2004
            record = WhatsAppMessage(
                conversation_id=conversation.id,
                sender=sender,
                body=preview,
                encrypted_body=encrypted,
                message_type=msg.get("type", "text"),
                is_from_me=msg.get("is_from_me", False),
            )
            db.add(record)
            stored += 1

        await db.commit()

    logger.info("whatsapp_sync_messages_stored", count=stored)
    return {"status": "ok", "messages_stored": stored}
