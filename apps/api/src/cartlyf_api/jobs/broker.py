from uuid import UUID

import dramatiq
import redis
from dramatiq import Broker, Message
from dramatiq.brokers.redis import RedisBroker

SOLVE_QUEUE = "solves"
SOLVE_ACTOR = "solve_run"


def make_broker(redis_url: str, timeout_seconds: float) -> RedisBroker:
    # RedisBroker ignores connection parameters when given a url, so build the pool here.
    pool = redis.ConnectionPool.from_url(  # pyright: ignore[reportUnknownMemberType]
        redis_url, socket_timeout=timeout_seconds, socket_connect_timeout=timeout_seconds
    )
    return RedisBroker(connection_pool=pool)


def setup_broker(redis_url: str, timeout_seconds: float) -> RedisBroker:
    broker = make_broker(redis_url, timeout_seconds)
    dramatiq.set_broker(broker)
    return broker


def send_solve(broker: Broker, run_id: UUID, organisation_id: UUID) -> None:
    broker.enqueue(  # pyright: ignore[reportUnknownMemberType]
        Message(
            queue_name=SOLVE_QUEUE,
            actor_name=SOLVE_ACTOR,
            args=(str(run_id), str(organisation_id)),
            kwargs={},
            options={},
        )
    )
