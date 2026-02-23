"""DailyBriefing model — aggregated daily digests."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class DailyBriefing(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "daily_briefings"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    briefing_date: Mapped[date] = mapped_column(Date, nullable=False)
    finance_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    email_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    calendar_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    health_summary: Mapped[str | None] = mapped_column(Text, nullable=True)
    recommendations: Mapped[dict | None] = mapped_column(JSONB, nullable=True)
