"""Fixed-window login rate limiting backed by Redis."""

import hashlib
import logging

from app.core.config import settings
from app.core.errors import AppError
from app.core.redis import get_redis

logger = logging.getLogger("fogroom.ratelimit")


async def check_login_rate(client_ip: str, email: str) -> None:
    digest = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    key = f"fogroom:rl:login:{client_ip}:{digest}"
    try:
        redis = get_redis()
        count = await redis.incr(key)
        if count == 1:
            await redis.expire(key, settings.login_rate_window_seconds)
    except Exception:  # fail open: availability over strictness for a training tool
        logger.warning("Rate limiter unavailable; allowing login attempt")
        return
    if count > settings.login_rate_limit:
        raise AppError(
            "RATE_LIMITED",
            "Too many login attempts. Please wait a few minutes and try again.",
            429,
            {"retry_after_seconds": settings.login_rate_window_seconds},
        )


async def reset_login_rate(client_ip: str, email: str) -> None:
    digest = hashlib.sha256(email.lower().encode()).hexdigest()[:16]
    try:
        await get_redis().delete(f"fogroom:rl:login:{client_ip}:{digest}")
    except Exception:
        logger.debug("Could not reset rate limit counter", exc_info=True)
