import asyncio

import pytest

from cartlyf_api.errors import RateLimited, ServiceUnavailable
from cartlyf_api.rate_limit import enforce
from cartlyf_api.redis_client import connect_redis


@pytest.mark.integration
def test_limit_blocks_after_n_hits_in_window(redis_url: str) -> None:
    async def run() -> None:
        redis = connect_redis(redis_url)
        try:
            for _ in range(3):
                await enforce(redis, "t:k", limit=3, window_seconds=60, now=120.0)
            with pytest.raises(RateLimited) as caught:
                await enforce(redis, "t:k", limit=3, window_seconds=60, now=130.0)
            assert caught.value.retry_after == 50
            await enforce(redis, "t:k", limit=3, window_seconds=60, now=181.0)
            await enforce(redis, "t:other", limit=3, window_seconds=60, now=130.0)
        finally:
            await redis.aclose()

    asyncio.run(run())


def test_redis_down_fails_closed() -> None:
    async def run() -> None:
        redis = connect_redis("redis://127.0.0.1:1/0", timeout_seconds=1)
        try:
            with pytest.raises(ServiceUnavailable):
                await enforce(redis, "t:k", limit=3, window_seconds=60, now=0.0)
        finally:
            await redis.aclose()

    asyncio.run(run())
