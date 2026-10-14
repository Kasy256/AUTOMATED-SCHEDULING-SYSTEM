import asyncio
from uuid import UUID, uuid4

import structlog
from dramatiq import Broker
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import (
    Conflict,
    NotFound,
    RateLimited,
    ServiceUnavailable,
    Unprocessable,
    field_error,
)
from cartlyf_api.jobs.broker import send_solve
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.settings import Settings
from cartlyf_api.solves import repository
from cartlyf_api.solves.models import SolveRun
from cartlyf_api.solves.schemas import SolveRequest, SolveRunResponse
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_engine.domain import SolveOptions

log = structlog.get_logger()


def _response(run: SolveRun) -> SolveRunResponse:
    return SolveRunResponse.model_validate(run)


async def _sweep(session: AsyncSession, settings: Settings, org: UUID) -> None:
    await repository.fail_stale_runs(
        session, org, settings.solve_stale_after_seconds, settings.solve_queue_timeout_seconds
    )


async def _require_schedule(session: AsyncSession, org: UUID, schedule_id: UUID) -> None:
    if await schedules_repo.get_schedule(session, org, schedule_id) is None:
        raise NotFound("Unknown schedule")


async def request_solve(
    engine: AsyncEngine,
    broker: Broker,
    settings: Settings,
    principal: Principal,
    schedule_id: UUID,
    body: SolveRequest,
) -> SolveRunResponse:
    principal.require(Permission.SOLVES_RUN)
    org = principal.organisation_id
    time_limit = body.time_limit_s or settings.solve_default_time_limit_s
    if time_limit > settings.solve_max_time_limit_s:
        raise Unprocessable(
            [
                field_error(
                    ("body", "time_limit_s"), f"must be at most {settings.solve_max_time_limit_s}"
                )
            ]
        )
    run_id = uuid4()
    async with scoped_transaction(engine, org, principal.user_id) as session:
        await _require_schedule(session, org, schedule_id)
        await repository.lock_org_runs(session, org)
        await _sweep(session, settings, org)
        if await repository.count_active(session, org) >= settings.solve_max_concurrent_per_org:
            raise RateLimited(
                settings.solve_stale_after_seconds,
                "Too many solves running for this organisation",
            )
        snapshot = await build_snapshot(session, org, schedule_id)
        options = SolveOptions(
            time_limit_s=time_limit, seed=body.seed, num_workers=settings.solve_num_workers
        )
        await repository.insert_run(
            session,
            run_id=run_id,
            org=org,
            schedule_id=schedule_id,
            user_id=principal.user_id,
            snapshot=snapshot,
            options=options,
        )
        await record_change(
            session,
            principal,
            "solve.requested",
            "solve_run",
            run_id,
            {"schedule_id": str(schedule_id)},
        )
        run = await repository.get_run(session, org, run_id)
        assert run is not None
        response = _response(run)
    try:
        await asyncio.to_thread(send_solve, broker, run_id, org)
    except Exception:
        log.exception("solve_enqueue_failed", run_id=str(run_id))
        async with scoped_transaction(engine, org, principal.user_id) as session:
            stored = await repository.get_run(session, org, run_id, for_update=True)
            assert stored is not None
            await repository.finish(session, stored, "failed", error="Could not queue the solve")
        raise ServiceUnavailable("Solve queue unavailable") from None
    return response


async def get_run(
    session: AsyncSession, settings: Settings, principal: Principal, run_id: UUID
) -> SolveRunResponse:
    principal.require(Permission.VERSIONS_READ)
    org = principal.organisation_id
    await _sweep(session, settings, org)
    run = await repository.get_run(session, org, run_id)
    if run is None:
        raise NotFound("Unknown solve run")
    return _response(run)


async def list_runs(
    session: AsyncSession, settings: Settings, principal: Principal, schedule_id: UUID
) -> list[SolveRunResponse]:
    principal.require(Permission.VERSIONS_READ)
    org = principal.organisation_id
    await _require_schedule(session, org, schedule_id)
    await _sweep(session, settings, org)
    return [_response(run) for run in await repository.list_runs(session, org, schedule_id)]


async def cancel_run(session: AsyncSession, principal: Principal, run_id: UUID) -> SolveRunResponse:
    principal.require(Permission.SOLVES_RUN)
    org = principal.organisation_id
    run = await repository.get_run(session, org, run_id, for_update=True)
    if run is None:
        raise NotFound("Unknown solve run")
    if run.status == "queued":
        await repository.finish(session, run, "cancelled")
    elif run.status == "running":
        if run.cancel_requested_at is None:
            run.cancel_requested_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
            await session.flush()
            await session.refresh(run)
    else:
        raise Conflict("Run already finished")
    await record_change(session, principal, "solve.cancel_requested", "solve_run", run_id)
    return _response(run)
