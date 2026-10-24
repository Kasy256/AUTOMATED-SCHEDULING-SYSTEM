import importlib
import sys
from typing import cast

import pytest
import redis
import structlog
from dramatiq import Worker
from testcontainers.community.redis import RedisContainer

from cartlyf_api.jobs.broker import make_broker, setup_broker

pytestmark = pytest.mark.integration


def test_worker_runs_ping_through_redis() -> None:
    with RedisContainer("redis:7-alpine") as redis:
        url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        broker = setup_broker(url, timeout_seconds=5)
        # Dramatiq binds actors to the global broker at import time, so (re)import after setup.
        loaded = sys.modules.get("cartlyf_api.jobs.actors")
        actors = (
            importlib.reload(loaded)
            if loaded
            else importlib.import_module("cartlyf_api.jobs.actors")
        )
        worker = Worker(broker, worker_timeout=100)
        with structlog.testing.capture_logs() as logs:
            actors.ping.send()
            worker.start()
            try:
                broker.join(actors.ping.queue_name, timeout=10_000)
                worker.join()
            finally:
                worker.stop()
    assert {"event": "ping", "log_level": "info"} in logs


def test_broker_redis_connections_have_bounded_timeouts() -> None:
    broker = make_broker("redis://127.0.0.1:1/0", timeout_seconds=2.5)
    client = cast(redis.Redis, broker.client)  # pyright: ignore[reportUnknownMemberType]
    kwargs = client.connection_pool.connection_kwargs
    assert kwargs["socket_timeout"] == 2.5
    assert kwargs["socket_connect_timeout"] == 2.5
