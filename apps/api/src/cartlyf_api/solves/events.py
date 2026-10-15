import asyncio
import contextlib
import json
import time
from collections.abc import AsyncIterator, Mapping
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncEngine

from cartlyf_api.auth.permissions import Principal
from cartlyf_api.settings import Settings
from cartlyf_api.solves import repository
from cartlyf_api.solves.notifier import SolveNotifier
from cartlyf_api.solves.schemas import ACTIVE
from cartlyf_api.tenancy import scoped_transaction

log = structlog.get_logger()

# Below typical proxy idle timeouts, so an idle stream is not cut between heartbeats.
KEEP_ALIVE_SECONDS = 15
KEEP_ALIVE = ": keep-alive\n\n"


def sse(event: str, data: Mapping[str, object]) -> str:
    return f"event: {event}\ndata: {json.dumps(data, separators=(',', ':'))}\n\n"


async def _read(
    engine: AsyncEngine, settings: Settings, principal: Principal, run_id: UUID
) -> tuple[str, dict[str, object], str | None, str | None] | None:
    org = principal.organisation_id
    async with scoped_transaction(engine, org, principal.user_id) as session:
        await repository.fail_stale_runs(
            session, org, settings.solve_stale_after_seconds, settings.solve_queue_timeout_seconds
        )
        run = await repository.get_run(session, org, run_id)
        if run is None:
            return None
        version = str(run.version_id) if run.version_id else None
        return run.status, dict(run.progress), version, run.error


async def run_events(
    engine: AsyncEngine,
    notifier: SolveNotifier,
    settings: Settings,
    principal: Principal,
    run_id: UUID,
) -> AsyncIterator[str]:
    try:
        async with notifier.subscribe(run_id) as changed:
            last: tuple[str, dict[str, object]] | None = None
            last_sent = time.monotonic()
            while True:
                changed.clear()
                row = await _read(engine, settings, principal, run_id)
                if row is None:
                    return
                status, progress, version_id, error = row
                if last != (status, progress):
                    last = (status, progress)
                    last_sent = time.monotonic()
                    yield sse("progress", {"status": status, **progress})
                if status not in ACTIVE:
                    yield sse("done", {"status": status, "version_id": version_id, "error": error})
                    return
                with contextlib.suppress(TimeoutError):
                    await asyncio.wait_for(changed.wait(), settings.solve_heartbeat_seconds)
                await notifier.ensure_listening()
                if time.monotonic() - last_sent >= KEEP_ALIVE_SECONDS:
                    last_sent = time.monotonic()
                    yield KEEP_ALIVE
    except Exception:
        log.exception("solve_events_failed", run_id=str(run_id))
