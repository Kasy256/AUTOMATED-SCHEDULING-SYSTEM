"""Worker body for one solve run: claim, solve with heartbeat, verify, store."""

import asyncio
import threading
from collections.abc import Callable
from dataclasses import dataclass, field
from uuid import UUID

import structlog
from sqlalchemy import func, text, update
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from cartlyf_api.db import JsonDict
from cartlyf_api.sentry import report_failed_verification, report_worker_error
from cartlyf_api.settings import Settings
from cartlyf_api.solves import repository
from cartlyf_api.solves.models import SolveRun
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_api.versions.persist import write_version
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Score, Solution, SolveOptions, SolveStatus
from cartlyf_engine.infeasibility import diagnose
from cartlyf_engine.solve import CancelToken, Progress, ProgressFn, solve
from cartlyf_engine.templates.registry import UnsupportedTemplate

log = structlog.get_logger()

SolveFn = Callable[[Problem, SolveOptions | None, ProgressFn | None, CancelToken | None], Solution]

_NOTIFY = text("SELECT pg_notify('solve_run', :id)")


@dataclass
class _Latest:
    """Latest progress from the solver thread, merged so a bound keeps the last objective."""

    _lock: threading.Lock = field(default_factory=threading.Lock)
    _progress: Progress | None = None
    _fresh: bool = False

    def set(self, progress: Progress) -> None:
        if progress.kind == "log":
            return
        with self._lock:
            if progress.kind == "bound" and self._progress is not None:
                progress = self._progress.model_copy(
                    update={"kind": "bound", "best_bound": progress.best_bound}
                )
            self._progress, self._fresh = progress, True

    def take(self) -> Progress | None:
        with self._lock:
            fresh, self._fresh = self._fresh, False
            return self._progress if fresh else None


@dataclass(frozen=True)
class _Verified:
    problem: Problem
    solution: Solution
    score: Score


@dataclass(frozen=True)
class _Outcome:
    status: str
    error: str | None = None
    conflicts: tuple[str, ...] = ()
    verified: _Verified | None = None
    infeasibility: JsonDict | None = None


def _progress_json(progress: Progress) -> JsonDict:
    return progress.model_dump(
        mode="json", include={"kind", "objective", "best_bound", "solutions", "wall_time_s"}
    )


async def _notify(session: AsyncSession, run_id: UUID) -> None:
    await session.execute(_NOTIFY, {"id": str(run_id)})


async def execute_run(
    engine: AsyncEngine,
    settings: Settings,
    run_id: UUID,
    organisation_id: UUID,
    solve_fn: SolveFn = solve,
) -> str:
    """Run one queued solve; returns its final status, or "skipped" if it was not ours to run."""
    claimed = await _claim(engine, settings, run_id, organisation_id)
    if isinstance(claimed, str):
        return claimed
    latest = _Latest()
    outcome = await _solve(engine, settings, run_id, organisation_id, claimed, solve_fn, latest)
    return await _finish(engine, run_id, organisation_id, outcome, latest.take())


async def _claim(
    engine: AsyncEngine, settings: Settings, run_id: UUID, org: UUID
) -> JsonDict | str:
    """Move queued -> running under the row lock; any other state means another owner."""
    async with scoped_transaction(engine, org) as session:
        run = await repository.get_run(session, org, run_id, for_update=True)
        if run is None:
            log.warning("solve_run_not_found", run_id=str(run_id), organisation_id=str(org))
            return "skipped"
        if run.status == "running":
            # A redelivery: the first delivery may still be solving, so only a silent run fails.
            await repository.fail_stale_runs(
                session,
                org,
                settings.solve_stale_after_seconds,
                settings.solve_queue_timeout_seconds,
            )
            return "skipped"
        if run.status != "queued":
            return "skipped"
        if run.cancel_requested_at is not None:
            await repository.finish(session, run, "cancelled")
            await _notify(session, run_id)
            return "cancelled"
        run.status = "running"
        run.started_at = run.heartbeat_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
        await session.flush()
        await _notify(session, run_id)
        return run.problem


async def _solve(
    engine: AsyncEngine,
    settings: Settings,
    run_id: UUID,
    org: UUID,
    problem_json: JsonDict,
    solve_fn: SolveFn,
    latest: _Latest,
) -> _Outcome:
    token = CancelToken()
    try:
        problem = Problem.model_validate(problem_json)
        solution = await _with_heartbeat(
            engine,
            settings,
            run_id,
            org,
            latest,
            token,
            lambda: solve_fn(problem, None, latest.set, token),
        )
        if solution.status is SolveStatus.INFEASIBLE:
            report = await _diagnose(engine, settings, run_id, org, problem, latest, token)
            return _Outcome("infeasible", conflicts=solution.conflicts, infeasibility=report)
        if not solution.assignments:
            return _Outcome("cancelled" if token.cancelled else "no_solution")
        # The independent re-check: the solver's own score is never trusted.
        score = await asyncio.to_thread(check, problem, solution.assignments)
    except UnsupportedTemplate as exc:
        return _Outcome("failed", error=f"Rule '{exc.key}' is not supported yet")
    except Exception as exc:
        report_worker_error(run_id, org, exc)
        return _Outcome("failed", error="The solver stopped unexpectedly")
    if score.hard_violations > 0:
        report_failed_verification(run_id, org, score.hard_violations)
        return _Outcome("failed_verification", error="The result failed verification")
    status = "cancelled" if token.cancelled else "succeeded"
    return _Outcome(status, verified=_Verified(problem, solution, score))


async def _diagnose(
    engine: AsyncEngine,
    settings: Settings,
    run_id: UUID,
    org: UUID,
    problem: Problem,
    latest: _Latest,
    token: CancelToken,
) -> JsonDict | None:
    """A failed diagnosis must not turn an infeasible result into a failed run."""
    try:
        report = await _with_heartbeat(
            engine,
            settings,
            run_id,
            org,
            latest,
            token,
            lambda: diagnose(problem, settings.infeasibility_time_limit_s, token),
        )
    except Exception as exc:
        report_worker_error(run_id, org, exc)
        return None
    return report.model_dump(mode="json")


async def _with_heartbeat[T](
    engine: AsyncEngine,
    settings: Settings,
    run_id: UUID,
    org: UUID,
    latest: _Latest,
    token: CancelToken,
    work: Callable[[], T],
) -> T:
    task = asyncio.create_task(asyncio.to_thread(work))
    try:
        while not task.done():
            await asyncio.wait({task}, timeout=settings.solve_heartbeat_seconds)
            # Cancel again on every beat: a stop sent before CP-SAT's search starts is lost.
            if not task.done() and not await _beat(engine, run_id, org, latest.take()):
                token.cancel()
    except BaseException:
        token.cancel()
        await asyncio.wait({task})
        raise
    return task.result()


async def _beat(engine: AsyncEngine, run_id: UUID, org: UUID, progress: Progress | None) -> bool:
    # A transient DB fault must not kill a long solve; the stale sweep is the liveness backstop.
    try:
        return await _heartbeat(engine, run_id, org, progress)
    except (SQLAlchemyError, OSError, TimeoutError):
        log.warning("solve_heartbeat_failed", run_id=str(run_id), exc_info=True)
        return True


async def _heartbeat(
    engine: AsyncEngine, run_id: UUID, org: UUID, progress: Progress | None
) -> bool:
    """Record liveness and progress; False once the run is cancelled or finished elsewhere."""
    values: JsonDict = {"heartbeat_at": func.now()}
    if progress is not None:
        values["progress"] = _progress_json(progress)
    async with scoped_transaction(engine, org) as session:
        row = (
            await session.execute(
                update(SolveRun)
                .where(
                    SolveRun.organisation_id == org,
                    SolveRun.id == run_id,
                    SolveRun.status == "running",
                )
                .values(values)
                .returning(SolveRun.cancel_requested_at)
            )
        ).one_or_none()
        await _notify(session, run_id)
    return row is not None and row.cancel_requested_at is None


async def _finish(
    engine: AsyncEngine, run_id: UUID, org: UUID, outcome: _Outcome, progress: Progress | None
) -> str:
    async with scoped_transaction(engine, org) as session:
        run = await repository.get_run(session, org, run_id, for_update=True)
        if run is None:
            return "skipped"
        if run.status != "running":
            # The stale sweep (or an operator) already ended it; its verdict stands.
            log.warning("solve_run_already_finished", run_id=str(run_id), status=run.status)
            return run.status
        version_id = None
        if outcome.verified is not None:
            verified = outcome.verified
            version_id = await write_version(
                session,
                org=org,
                schedule_id=run.schedule_id,
                run=run,
                parent_id=run.baseline_version_id,
                solver_status=verified.solution.status.value,
                assignments=verified.solution.assignments,
                score=verified.score,
                origin=run.horizon_origin,
                problem=verified.problem,
                user_id=run.requested_by,
            )
        if progress is not None:
            run.progress = _progress_json(progress)
        await repository.finish(
            session,
            run,
            outcome.status,
            error=outcome.error,
            conflicts=outcome.conflicts,
            infeasibility=outcome.infeasibility,
            version_id=version_id,
        )
        await _notify(session, run_id)
    log.info("solve_run_finished", run_id=str(run_id), status=outcome.status)
    return outcome.status
