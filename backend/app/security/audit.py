"""Audit logging — records all API access to an append-only table."""

from __future__ import annotations

import uuid

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.audit import AuditLog

logger = structlog.get_logger()


async def audit_log(
    db: AsyncSession,
    *,
    action: str,
    resource_type: str,
    resource_id: str | None = None,
    user_id: uuid.UUID | None = None,
    ip_address: str | None = None,
    metadata: dict | None = None,
    detail: str | None = None,
) -> AuditLog:
    """Write an audit log entry. Append-only — never update or delete."""
    entry = AuditLog(
        user_id=user_id,
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        ip_address=ip_address,
        metadata_=metadata,
        detail=detail,
    )
    db.add(entry)
    await db.flush()

    logger.info(
        "audit",
        action=action,
        resource_type=resource_type,
        resource_id=resource_id,
        user_id=str(user_id) if user_id else None,
    )

    return entry
