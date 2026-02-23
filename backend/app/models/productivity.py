"""ProductivityLog model — device and app usage tracking."""

from __future__ import annotations

import uuid
from datetime import date

from sqlalchemy import Date, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base, TimestampMixin, UUIDMixin


class ProductivityLog(UUIDMixin, TimestampMixin, Base):
    __tablename__ = "productivity_logs"

    user_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    device: Mapped[str] = mapped_column(String(50), nullable=False)
    app_name: Mapped[str] = mapped_column(String(255), nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    category: Mapped[str] = mapped_column(String(50), default="uncategorized")
    log_date: Mapped[date] = mapped_column(Date, nullable=False)
