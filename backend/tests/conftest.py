"""Shared test fixtures for ClawdBot backend."""

from __future__ import annotations

import os
import uuid

import pytest
from httpx import ASGITransport, AsyncClient

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("JWT_SECRET", "test_jwt_secret_0123456789abcdef")
os.environ.setdefault(
    "ENCRYPTION_MASTER_KEY",
    "0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
)
os.environ.setdefault("POSTGRES_PASSWORD", "test")
os.environ.setdefault("REDIS_PASSWORD", "test")

from app.main import app  # noqa: E402
from app.security import rate_limit as _rate_limit_mod  # noqa: E402
from app.security.auth import hash_password  # noqa: E402


@pytest.fixture
def master_key() -> bytes:
    return bytes.fromhex("0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef")


@pytest.fixture
def sample_user_id() -> str:
    return str(uuid.uuid4())


@pytest.fixture
def hashed_pw() -> str:
    return hash_password("testpassword123")


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Disable Redis-backed rate limiting in tests.

    Replace the module-level Redis client with a mock that raises
    ConnectionError, causing the rate limiter to fail open (allow the request).
    This prevents stale sorted-set state from leaking between tests.
    """
    from unittest.mock import AsyncMock, MagicMock

    # Pipeline mock for rate limiter (synchronous chaining, async execute).
    mock_pipe = MagicMock()
    mock_pipe.zremrangebyscore.return_value = mock_pipe
    mock_pipe.zadd.return_value = mock_pipe
    mock_pipe.zcard.return_value = mock_pipe
    mock_pipe.expire.return_value = mock_pipe
    mock_pipe.execute = AsyncMock(return_value=[0, True, 1, True])

    # Redis mock — MagicMock for pipeline(), AsyncMock for token blocklist ops.
    mock_redis = MagicMock()
    mock_redis.pipeline.return_value = mock_pipe
    mock_redis.exists = AsyncMock(return_value=0)
    mock_redis.setex = AsyncMock(return_value=True)
    _rate_limit_mod._redis_client = mock_redis
    yield
    _rate_limit_mod._redis_client = None


@pytest.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
