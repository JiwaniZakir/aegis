"""Security dashboard endpoints — audit logs, sessions, failed logins, 2FA, password change."""

from __future__ import annotations

import uuid

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import desc, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user, get_db
from app.models.audit import AuditLog
from app.models.user import User
from app.security.auth import hash_password, verify_password

logger = structlog.get_logger()

router = APIRouter(prefix="/security", tags=["security"])


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class ChangePasswordRequest(BaseModel):
    current_password: str = Field(min_length=1)
    new_password: str = Field(min_length=12, max_length=128)


# ---------------------------------------------------------------------------
# Audit log
# ---------------------------------------------------------------------------


@router.get("/audit-log")
async def get_audit_log(
    limit: int = Query(50, ge=1, le=200),
    offset: int = Query(0, ge=0),
    action: str | None = Query(None),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Paginated audit log viewer."""
    query = select(AuditLog).order_by(desc(AuditLog.timestamp))

    if action:
        query = query.where(AuditLog.action == action)

    count_query = select(func.count()).select_from(AuditLog)
    if action:
        count_query = count_query.where(AuditLog.action == action)

    total_result = await db.execute(count_query)
    total = total_result.scalar() or 0

    result = await db.execute(query.offset(offset).limit(limit))
    entries = result.scalars().all()

    return {
        "entries": [
            {
                "id": str(e.id),
                "timestamp": e.timestamp.isoformat(),
                "action": e.action,
                "resource": f"{e.resource_type}:{e.resource_id or ''}",
                "ip_address": e.ip_address or "",
                "user_agent": (e.metadata_ or {}).get("user_agent", ""),
                "status": "failure" if "failed" in e.action else "success",
            }
            for e in entries
        ],
        "total": total,
    }


# ---------------------------------------------------------------------------
# Active sessions (approximated from recent auth audit entries)
# ---------------------------------------------------------------------------


@router.get("/sessions")
async def get_active_sessions(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """List recent login sessions from audit log."""
    result = await db.execute(
        select(AuditLog)
        .where(
            AuditLog.action == "login_success",
            AuditLog.user_id == user.id,
        )
        .order_by(desc(AuditLog.timestamp))
        .limit(20)
    )
    sessions = result.scalars().all()

    return [
        {
            "id": str(s.id),
            "ip_address": s.ip_address or "",
            "user_agent": (s.metadata_ or {}).get("user_agent", ""),
            "created_at": s.timestamp.isoformat(),
            "last_active": s.timestamp.isoformat(),
            "is_current": False,
        }
        for s in sessions
    ]


@router.delete("/sessions/{session_id}")
async def revoke_session(
    session_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Revoke a session (placeholder — actual token revocation via blocklist)."""
    try:
        uuid.UUID(session_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Invalid session ID") from exc

    from app.security.audit import audit_log

    await audit_log(
        db,
        action="session_revoked",
        resource_type="security",
        resource_id=session_id,
        user_id=user.id,
    )
    await db.commit()

    return {"revoked": True, "session_id": session_id}


# ---------------------------------------------------------------------------
# Failed logins
# ---------------------------------------------------------------------------


@router.get("/failed-logins")
async def get_failed_logins(
    limit: int = Query(20, ge=1, le=100),
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> list[dict]:
    """Recent failed login attempts."""
    result = await db.execute(
        select(AuditLog)
        .where(AuditLog.action.in_(["login_failed", "login_failed_totp"]))
        .order_by(desc(AuditLog.timestamp))
        .limit(limit)
    )
    entries = result.scalars().all()

    return [
        {
            "id": str(e.id),
            "timestamp": e.timestamp.isoformat(),
            "action": e.action,
            "resource": f"{e.resource_type}:{e.resource_id or ''}",
            "ip_address": e.ip_address or "",
            "user_agent": (e.metadata_ or {}).get("user_agent", ""),
            "status": "failure",
        }
        for e in entries
    ]


# ---------------------------------------------------------------------------
# 2FA status
# ---------------------------------------------------------------------------


@router.get("/2fa/status")
async def get_2fa_status(
    user: User = Depends(get_current_user),
) -> dict:
    """Check whether 2FA is enabled for the current user."""
    return {
        "enabled": bool(user.totp_secret),
        "method": "totp" if user.totp_secret else "none",
        "last_verified": None,
    }


# ---------------------------------------------------------------------------
# Change password
# ---------------------------------------------------------------------------


@router.post("/change-password", status_code=status.HTTP_204_NO_CONTENT)
async def change_password(
    body: ChangePasswordRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Change the admin password. Requires current password verification."""
    if not verify_password(body.current_password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Current password is incorrect",
        )

    user.hashed_password = hash_password(body.new_password)

    from app.security.audit import audit_log

    await audit_log(
        db,
        action="password_changed",
        resource_type="security",
        user_id=user.id,
    )
    await db.commit()
