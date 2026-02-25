"""Authentication endpoints — login, token refresh, logout."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.user import User
from app.security.audit import audit_log
from app.security.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    get_current_user,
    verify_password,
    verify_totp,
)
from app.security.rate_limit import check_rate_limit
from app.security.token_blocklist import block_token

router = APIRouter(prefix="/auth", tags=["auth"])
bearer_scheme = HTTPBearer()

# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------


class LoginRequest(BaseModel):
    email: str
    password: str
    totp_code: str | None = None


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"  # noqa: S105
    expires_in: int = 900  # 15 minutes in seconds


class RefreshRequest(BaseModel):
    refresh_token: str


class LogoutRequest(BaseModel):
    refresh_token: str | None = None


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("/login", response_model=TokenResponse)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Authenticate with email + password (+ optional TOTP).

    Rate-limited to 5 attempts per minute per client IP to mitigate
    brute-force attacks.
    """
    from app.security.monitoring import (
        clear_failed_logins,
        is_locked_out,
        record_failed_login,
    )

    # Fix 1: strict rate limiting on login (5 attempts / 60 seconds)
    await check_rate_limit(request, limit=5, window_seconds=60)

    # Check account lockout (10 failed attempts = 15 min lockout)
    if await is_locked_out(body.email):
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Account temporarily locked due to too many failed attempts",
        )

    result = await db.execute(select(User).where(User.email == body.email))
    user = result.scalar_one_or_none()

    # Always run bcrypt to prevent user-enumeration via timing side-channel.
    # When the user doesn't exist we verify against a dummy hash so the
    # response time is indistinguishable from a wrong-password attempt.
    _dummy_hash = "$2b$12$LJ3m4ys3Lg2HEgOsvKSMxeq9HsRMsxTdWkFjo/TqUWGpBguQp6sca"
    password_valid = verify_password(
        body.password,
        user.hashed_password if user else _dummy_hash,
    )

    if user is None or not password_valid:
        await record_failed_login(body.email)
        await audit_log(
            db,
            action="login_failed",
            resource_type="auth",
            detail="Failed login attempt",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid credentials",
        )

    if user.totp_secret:
        if not body.totp_code:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="TOTP code required",
            )
        if not verify_totp(user.totp_secret, body.totp_code):
            await audit_log(
                db,
                action="login_failed_totp",
                resource_type="auth",
                user_id=user.id,
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Invalid TOTP code",
            )

    # Clear lockout counter on successful login
    await clear_failed_logins(body.email)

    user_id = str(user.id)
    access_token = create_access_token(user_id)
    refresh_token = create_refresh_token(user_id)

    await audit_log(
        db,
        action="login_success",
        resource_type="auth",
        user_id=user.id,
    )

    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
    )


@router.post("/refresh", response_model=TokenResponse)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
) -> TokenResponse:
    """Exchange a refresh token for a new access/refresh pair.

    Fix 2: After decoding the JWT the endpoint now verifies that the
    referenced user still exists and is active before issuing new tokens.
    """
    payload = await decode_token(body.refresh_token)

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token type",
        )

    user_id = payload["sub"]

    # Fix 2: verify user exists and is still active
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()

    if user is None or not user.is_active:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found or inactive",
        )

    return TokenResponse(
        access_token=create_access_token(str(user.id)),
        refresh_token=create_refresh_token(str(user.id)),
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
async def logout(
    body: LogoutRequest,
    credentials: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db),
) -> None:
    """Revoke the current access token and (optionally) a refresh token.

    Fix 3: Adds the JTIs to a Redis-backed blocklist so that subsequent
    use of these tokens is rejected by ``decode_token``.
    """
    # Block the access token from the Authorization header
    access_payload = await decode_token(credentials.credentials)
    access_jti = access_payload.get("jti")
    if access_jti:
        # TTL = remaining seconds until the token would expire naturally
        exp = access_payload.get("exp", 0)
        ttl = max(int(exp - datetime.now(UTC).timestamp()), 0)
        await block_token(access_jti, ttl_seconds=ttl)

    # Optionally block the refresh token as well
    if body.refresh_token:
        refresh_payload = await decode_token(body.refresh_token)
        refresh_jti = refresh_payload.get("jti")
        if refresh_jti:
            exp = refresh_payload.get("exp", 0)
            ttl = max(int(exp - datetime.now(UTC).timestamp()), 0)
            await block_token(refresh_jti, ttl_seconds=ttl)

    await audit_log(
        db,
        action="logout",
        resource_type="auth",
        user_id=access_payload.get("sub"),
    )


@router.get("/me")
async def get_me(user: User = Depends(get_current_user)) -> dict:
    """Return the current authenticated user's profile."""
    return {
        "id": str(user.id),
        "email": user.email,
        "created_at": user.created_at.isoformat() if user.created_at else None,
    }
