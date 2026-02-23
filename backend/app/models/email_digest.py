"""EmailDigest model — email summaries and analysis."""

from __future__ import annotations

import uuid
from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class EmailDigest(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "email_digests"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    message_id: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    subject: Mapped[str] = mapped_column(String(500), nullable=False)
    sender: Mapped[str] = mapped_column(String(255), nullable=False)
    priority: Mapped[str] = mapped_column(String(20), default="informational")
    category: Mapped[str] = mapped_column(String(50), default="informational")
    encrypted_body_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
