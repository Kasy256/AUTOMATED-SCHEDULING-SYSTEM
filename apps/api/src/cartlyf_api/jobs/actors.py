import asyncio
from uuid import UUID

import dramatiq
import structlog

from cartlyf_api.db import create_db_engine
from cartlyf_api.jobs.broker import SOLVE_ACTOR, SOLVE_QUEUE
from cartlyf_api.settings import Settings, load_settings
from cartlyf_api.solves.runner import execute_run

log = structlog.get_logger()

# Dramatiq's TimeLimit cannot interrupt CP-SAT's native code; the solve's own time limit and the
# heartbeat sweep are the real bounds, so this only stops the default 10-minute limit firing.
_NO_DRAMATIQ_LIMIT_MS = 24 * 3600 * 1000


@dramatiq.actor
def ping() -> None:
    log.info("ping")


@dramatiq.actor(
    actor_name=SOLVE_ACTOR,
    queue_name=SOLVE_QUEUE,
    max_retries=0,
    time_limit=_NO_DRAMATIQ_LIMIT_MS,
)
def solve_run(run_id: str, organisation_id: str) -> None:
    settings = load_settings()
    asyncio.run(_run(settings, UUID(run_id), UUID(organisation_id)))


async def _run(settings: Settings, run_id: UUID, organisation_id: UUID) -> None:
    engine = create_db_engine(settings)
    try:
        await execute_run(engine, settings, run_id, organisation_id)
    finally:
        await engine.dispose()
