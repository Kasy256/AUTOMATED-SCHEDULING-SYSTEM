import importlib
import sys

import pytest
import structlog
from dramatiq import Worker
from testcontainers.community.redis import RedisContainer

from cartlyf_api.jobs.broker import setup_broker

pytestmark = pytest.mark.integration


def test_worker_runs_ping_through_redis() -> None:
    with RedisContainer("redis:7-alpine") as redis:
        url = f"redis://{redis.get_container_host_ip()}:{redis.get_exposed_port(6379)}/0"
        broker = setup_broker(url)
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
