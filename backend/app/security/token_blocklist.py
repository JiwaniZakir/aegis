"""Redis-backed JWT token blocklist for revocation."""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from app.security.rate_limit import get_redis

logger = structlog.get_logger()


async def block_token(jti: str, ttl_seconds: int) -> None:
    """Add a token's JTI to the blocklist with a TTL matching remaining lifetime.

    Uses Redis key ``token:blocked:{jti}`` so blocked tokens expire automatically
    once the original JWT would have expired anyway.
    """
    key = f"token:blocked:{jti}"
    try:
        r = await get_redis()
        await r.setex(key, ttl_seconds, "1")
        logger.info("token_blocked", jti=jti, ttl_seconds=ttl_seconds)
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError):
        logger.warning("token_blocklist_redis_unavailable", jti=jti)


async def is_token_blocked(jti: str) -> bool:
    """Check whether a token's JTI has been revoked.

    Returns ``True`` (fail-closed) when Redis is unavailable so that revoked
    tokens cannot bypass the blocklist during a transient outage.
    """
    key = f"token:blocked:{jti}"
    try:
        r = await get_redis()
        return await r.exists(key) > 0
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError):
        logger.error("token_blocklist_check_failed_denying_access", jti=jti)
        return True
