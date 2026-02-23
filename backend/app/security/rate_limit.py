"""Redis-backed sliding window rate limiter."""

from __future__ import annotations

import time
from collections.abc import Callable, Coroutine
from typing import Any

import redis.asyncio as aioredis
import structlog
from fastapi import HTTPException, Request, status

from app.config import get_settings

logger = structlog.get_logger()

_redis_client: aioredis.Redis | None = None


async def get_redis() -> aioredis.Redis:
    """Lazy-initialize a shared async Redis client."""
    global _redis_client  # noqa: PLW0603
    if _redis_client is None:
        settings = get_settings()
        _redis_client = aioredis.from_url(
            settings.redis_connection_url,
            decode_responses=True,
        )
    return _redis_client


async def check_rate_limit(
    request: Request,
    *,
    limit: int = 60,
    window_seconds: int = 60,
) -> None:
    """Sliding window rate limit check. Raises 429 if exceeded."""
    client_ip = request.client.host if request.client else "unknown"
    key = f"rate_limit:{client_ip}:{request.url.path}"

    try:
        r = await get_redis()
        now = time.time()
        window_start = now - window_seconds

        pipe = r.pipeline()
        pipe.zremrangebyscore(key, 0, window_start)
        pipe.zadd(key, {str(now): now})
        pipe.zcard(key)
        pipe.expire(key, window_seconds)
        results = await pipe.execute()

        current_count = results[2]

        if current_count > limit:
            logger.warning("rate_limit_exceeded", ip=client_ip, path=request.url.path)
            raise HTTPException(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                detail="Rate limit exceeded",
            )
    except HTTPException:
        raise
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError):
        logger.warning("rate_limit_redis_unavailable")


def rate_limit(
    limit: int = 60,
    window_seconds: int = 60,
) -> Callable[[Request], Coroutine[Any, Any, None]]:
    """FastAPI dependency factory for rate limiting.

    Usage::

        @router.post("/trade", dependencies=[Depends(rate_limit(limit=5, window_seconds=60))])
        async def initiate_trade(...): ...

    Args:
        limit: Maximum number of requests allowed within the window.
        window_seconds: Duration of the sliding window in seconds.

    Returns:
        An async callable suitable for ``Depends()``.
    """

    async def _dependency(request: Request) -> None:
        await check_rate_limit(request, limit=limit, window_seconds=window_seconds)

    return _dependency
