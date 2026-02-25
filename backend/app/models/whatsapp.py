"""WhatsApp message and conversation models."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class WhatsAppConversation(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_conversations"

    user_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[str] = mapped_column(String(50), nullable=False)
    is_group: Mapped[bool] = mapped_column(default=False)
    last_message_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    messages: Mapped[list[WhatsAppMessage]] = relationship(
        back_populates="conversation", lazy="selectin"
    )


class WhatsAppMessage(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "whatsapp_messages"

    conversation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("whatsapp_conversations.id", ondelete="CASCADE"),
        nullable=False,
    )
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    encrypted_body: Mapped[str | None] = mapped_column(Text, nullable=True)
    message_type: Mapped[str] = mapped_column(
        String(20), default="text"
    )  # text, image, audio, document
    timestamp: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    is_from_me: Mapped[bool] = mapped_column(default=False)

    conversation: Mapped[WhatsAppConversation] = relationship(back_populates="messages")
