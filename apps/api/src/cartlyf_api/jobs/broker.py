from uuid import UUID

import dramatiq
from dramatiq import Broker, Message
from dramatiq.brokers.redis import RedisBroker

SOLVE_QUEUE = "solves"
SOLVE_ACTOR = "solve_run"


def make_broker(redis_url: str) -> RedisBroker:
    return RedisBroker(url=redis_url)


def setup_broker(redis_url: str) -> RedisBroker:
    broker = make_broker(redis_url)
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
