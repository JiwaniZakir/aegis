"""WhatsApp endpoints — conversations, messages, sending, and bridge health."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Path, Query
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.integrations.whatsapp_bridge import WhatsAppBridgeClient, WhatsAppBridgeError
from app.models.user import User
from app.models.whatsapp import WhatsAppConversation, WhatsAppMessage
from app.security.encryption import decrypt_field

logger = structlog.get_logger()

router = APIRouter(tags=["whatsapp"])


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class SendMessageRequest(BaseModel):
    phone: str = Field(..., min_length=1, max_length=50, description="Recipient phone number")
    message: str = Field(..., min_length=1, max_length=4096, description="Message body")


class SendMessageResponse(BaseModel):
    status: str
    detail: dict | None = None


class ConversationOut(BaseModel):
    id: uuid.UUID
    contact_name: str
    contact_phone: str
    is_group: bool
    last_message_at: str | None = None
    message_count: int = 0

    model_config = {"from_attributes": True}


class MessageOut(BaseModel):
    id: uuid.UUID
    sender: str
    body: str
    message_type: str
    is_from_me: bool
    timestamp: str

    model_config = {"from_attributes": True}


class BridgeHealthResponse(BaseModel):
    bridge_available: bool


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.get("/whatsapp/health")
async def whatsapp_health(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> BridgeHealthResponse:
    """Check if the WhatsApp bridge sidecar is reachable."""
    client = WhatsAppBridgeClient(str(user.id), db)
    available = await client.health_check()
    return BridgeHealthResponse(bridge_available=available)


@router.get("/whatsapp/conversations")
async def list_conversations(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
) -> list[ConversationOut]:
    """List WhatsApp conversations for the authenticated user."""
    result = await db.execute(
        select(WhatsAppConversation)
        .where(WhatsAppConversation.user_id == user.id)
        .order_by(WhatsAppConversation.last_message_at.desc().nulls_last())
        .offset(offset)
        .limit(limit)
    )
    conversations = result.scalars().all()

    output: list[ConversationOut] = []
    for conv in conversations:
        msg_count = len(conv.messages) if conv.messages else 0
        output.append(
            ConversationOut(
                id=conv.id,
                contact_name=conv.contact_name,
                contact_phone=conv.contact_phone,
                is_group=conv.is_group,
                last_message_at=conv.last_message_at.isoformat() if conv.last_message_at else None,
                message_count=msg_count,
            )
        )
    return output


@router.get("/whatsapp/messages/{conversation_id}")
async def get_messages(
    conversation_id: uuid.UUID = Path(..., description="Conversation UUID"),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    limit: int = Query(50, ge=1, le=500),
    offset: int = Query(0, ge=0),
    decrypt: bool = Query(False, description="Return decrypted full message bodies"),
) -> list[MessageOut]:
    """Get messages for a specific WhatsApp conversation.

    By default returns truncated previews. Set ``decrypt=true`` to return
    the full decrypted message bodies (requires valid encryption key).
    """
    # Verify the conversation belongs to this user
    conv_result = await db.execute(
        select(WhatsAppConversation).where(
            WhatsAppConversation.id == conversation_id,
            WhatsAppConversation.user_id == user.id,
        )
    )
    conversation = conv_result.scalar_one_or_none()
    if conversation is None:
        raise HTTPException(status_code=404, detail="Conversation not found")

    result = await db.execute(
        select(WhatsAppMessage)
        .where(WhatsAppMessage.conversation_id == conversation_id)
        .order_by(WhatsAppMessage.timestamp.desc())
        .offset(offset)
        .limit(limit)
    )
    messages = result.scalars().all()

    output: list[MessageOut] = []
    for msg in messages:
        body = msg.body  # truncated preview by default

        if decrypt and msg.encrypted_body:
            try:
                from app.config import get_settings

                settings = get_settings()
                context = f"whatsapp:message:{conversation_id}"
                body = decrypt_field(
                    msg.encrypted_body, settings.master_key_bytes, context=context
                )
            except Exception:
                logger.warning(
                    "whatsapp_decrypt_failed",
                    message_id=str(msg.id),
                )
                # Fall back to preview
                body = msg.body

        output.append(
            MessageOut(
                id=msg.id,
                sender=msg.sender,
                body=body,
                message_type=msg.message_type,
                is_from_me=msg.is_from_me,
                timestamp=msg.timestamp.isoformat(),
            )
        )
    return output


@router.post("/whatsapp/send")
async def send_message(
    payload: SendMessageRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> SendMessageResponse:
    """Send a WhatsApp message via the bridge sidecar."""
    client = WhatsAppBridgeClient(str(user.id), db)

    try:
        result = await client.send_message(payload.phone, payload.message)
        return SendMessageResponse(status="sent", detail=result)
    except WhatsAppBridgeError as exc:
        logger.error("whatsapp_send_failed", error=str(exc))
        raise HTTPException(status_code=502, detail=str(exc)) from exc
