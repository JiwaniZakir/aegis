"""Security monitoring — failed login lockout and suspicious activity detection."""

from __future__ import annotations

import redis.asyncio as aioredis
import structlog

from app.security.rate_limit import get_redis

logger = structlog.get_logger()

# Lockout after this many failed attempts
MAX_FAILED_ATTEMPTS = 10
LOCKOUT_SECONDS = 900  # 15 minutes


async def record_failed_login(identifier: str) -> bool:
    """Record a failed login attempt. Returns True if account is now locked out."""
    key = f"failed_login:{identifier}"
    try:
        r = await get_redis()
        count = await r.incr(key)
        if count == 1:
            await r.expire(key, LOCKOUT_SECONDS)
        if count >= MAX_FAILED_ATTEMPTS:
            logger.warning(
                "account_locked_out",
                identifier=identifier,
                attempts=count,
            )
            return True
        return False
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError, TypeError):
        logger.warning("monitoring_redis_unavailable")
        return False


async def is_locked_out(identifier: str) -> bool:
    """Check if an identifier (email or IP) is currently locked out."""
    key = f"failed_login:{identifier}"
    try:
        r = await get_redis()
        count = await r.get(key)
        return count is not None and int(count) >= MAX_FAILED_ATTEMPTS
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError, TypeError):
        logger.warning("monitoring_redis_unavailable")
        return False


async def clear_failed_logins(identifier: str) -> None:
    """Clear failed login counter after successful login."""
    key = f"failed_login:{identifier}"
    try:
        r = await get_redis()
        await r.delete(key)
    except (aioredis.ConnectionError, aioredis.RedisError, OSError, RuntimeError, TypeError):
        logger.warning("monitoring_redis_unavailable")
