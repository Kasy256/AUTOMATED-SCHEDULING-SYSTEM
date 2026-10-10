from redis.asyncio import Redis


def connect_redis(url: str, timeout_seconds: float | None = None) -> Redis:
    # from_url's **kwargs are untyped in redis-py's stubs.
    return Redis.from_url(  # pyright: ignore[reportUnknownMemberType]
        url, socket_connect_timeout=timeout_seconds, socket_timeout=timeout_seconds
    )
