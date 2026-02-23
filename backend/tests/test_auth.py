"""Tests for JWT authentication, password hashing, and token blocklist."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pyotp
import pytest

from app.security.auth import (
    create_access_token,
    create_refresh_token,
    decode_token,
    generate_totp_secret,
    hash_password,
    verify_password,
    verify_totp,
)
from app.security.token_blocklist import block_token, is_token_blocked


def test_password_hash_and_verify():
    """Password hashing and verification round-trip."""
    pw = "strong_password_123!"
    hashed = hash_password(pw)
    assert hashed != pw
    assert verify_password(pw, hashed)
    assert not verify_password("wrong_password", hashed)


@pytest.mark.asyncio
async def test_access_token_roundtrip(sample_user_id: str):
    """Access token encodes and decodes user_id correctly."""
    token = create_access_token(sample_user_id)
    payload = await decode_token(token)
    assert payload["sub"] == sample_user_id
    assert payload["type"] == "access"
    assert "exp" in payload
    assert "jti" in payload


@pytest.mark.asyncio
async def test_refresh_token_roundtrip(sample_user_id: str):
    """Refresh token encodes and decodes with correct type."""
    token = create_refresh_token(sample_user_id)
    payload = await decode_token(token)
    assert payload["sub"] == sample_user_id
    assert payload["type"] == "refresh"


def test_totp_verify():
    """TOTP generation and verification works."""
    secret = generate_totp_secret()
    totp = pyotp.TOTP(secret)
    code = totp.now()
    assert verify_totp(secret, code)
    assert not verify_totp(secret, "000000")


@pytest.mark.asyncio
async def test_decode_token_invalid():
    """Decoding an invalid token raises HTTPException."""
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc_info:
        await decode_token("not.a.valid.token")
    assert exc_info.value.status_code == 401


@pytest.mark.asyncio
async def test_token_blocklist_failclosed_when_redis_unavailable():
    """Token blocklist denies access (fail-closed) when Redis is unavailable.

    Simulates Redis being unavailable by patching get_redis to raise
    ConnectionError. block_token should silently log a warning and
    is_token_blocked should return True (fail-closed) to prevent revoked
    tokens from being accepted during an outage.
    """
    import redis.asyncio as aioredis

    with patch(
        "app.security.token_blocklist.get_redis",
        side_effect=aioredis.ConnectionError("test: Redis unavailable"),
    ):
        # block_token should not raise when Redis is unavailable
        await block_token("test-jti-no-redis", ttl_seconds=300)

        # is_token_blocked should return True (fail-closed) when Redis is down
        assert await is_token_blocked("test-jti-no-redis") is True


@pytest.mark.asyncio
async def test_decode_token_checks_blocklist(sample_user_id: str):
    """decode_token returns payload when blocklist check passes."""
    from unittest.mock import AsyncMock

    with patch(
        "app.security.token_blocklist.is_token_blocked",
        new_callable=AsyncMock,
        return_value=False,
    ):
        token = create_access_token(sample_user_id)
        payload = await decode_token(token)
        assert payload["sub"] == sample_user_id
        assert "jti" in payload


@pytest.mark.asyncio
async def test_decode_token_rejects_blocked_token(sample_user_id: str):
    """decode_token raises 401 when token JTI is on the blocklist."""
    from fastapi import HTTPException

    token = create_access_token(sample_user_id)

    with patch(
        "app.security.token_blocklist.is_token_blocked",
        new_callable=AsyncMock,
        return_value=True,
    ):
        with pytest.raises(HTTPException) as exc_info:
            await decode_token(token)
        assert exc_info.value.status_code == 401
        assert "revoked" in exc_info.value.detail.lower()


@pytest.mark.asyncio
async def test_rate_limit_graceful_when_redis_unavailable():
    """Rate limiter degrades gracefully when Redis is unavailable."""
    from unittest.mock import MagicMock

    import redis.asyncio as aioredis

    from app.security.rate_limit import check_rate_limit

    # Build a minimal mock Request
    mock_request = MagicMock()
    mock_request.client.host = "127.0.0.1"
    mock_request.url.path = "/api/v1/auth/login"

    with patch(
        "app.security.rate_limit.get_redis",
        side_effect=aioredis.ConnectionError("test: Redis unavailable"),
    ):
        # Should not raise — graceful degradation
        await check_rate_limit(mock_request, limit=5, window_seconds=60)
