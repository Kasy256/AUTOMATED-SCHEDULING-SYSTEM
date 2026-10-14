import time
from collections.abc import Awaitable, Callable

from fastapi import Request
from redis.asyncio import Redis
from redis.exceptions import RedisError

from cartlyf_api.errors import RateLimited, ServiceUnavailable
from cartlyf_api.settings import Settings

WINDOW_SECONDS = 60


async def enforce(redis: Redis, key: str, limit: int, window_seconds: int, now: float) -> None:
    """Fixed-window counter: at most `limit` hits per key per window."""
    name = f"ratelimit:{key}:{int(now // window_seconds)}"
    try:
        async with redis.pipeline(transaction=True) as pipe:
            pipe.incr(name)
            pipe.expire(name, window_seconds)
            count, _ = await pipe.execute()
    except (RedisError, OSError) as exc:
        # Fail closed: without counters the auth endpoints would be open to brute force.
        raise ServiceUnavailable() from exc
    if count > limit:
        raise RateLimited(retry_after=window_seconds - int(now % window_seconds))


def _auth_limit(settings: Settings) -> int:
    return settings.auth_rate_limit_per_minute


def rate_limit(
    scope: str, limit: Callable[[Settings], int] = _auth_limit
) -> Callable[[Request], Awaitable[None]]:
    async def dependency(request: Request) -> None:
        client = request.client.host if request.client else "unknown"
        await enforce(
            request.app.state.redis,
            f"{scope}:ip:{client}",
            limit(request.app.state.settings),
            WINDOW_SECONDS,
            time.time(),
        )

    return dependency
