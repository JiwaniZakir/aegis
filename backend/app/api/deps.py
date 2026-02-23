"""Shared FastAPI dependencies."""

from __future__ import annotations

from app.database import get_db
from app.security.auth import get_current_user

__all__ = ["get_current_user", "get_db"]
