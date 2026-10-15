from collections.abc import Iterable, Sequence
from uuid import UUID

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.problems.snapshot import Snapshot
from cartlyf_api.solves.models import SolveRun
from cartlyf_api.solves.schemas import ACTIVE
from cartlyf_engine.domain import SolveOptions

_FAIL_STALE = text(
    """
    UPDATE solve_run SET status = 'failed', finished_at = now(),
      error = CASE WHEN status = 'running' THEN 'worker stopped responding'
                   ELSE 'never started' END
    WHERE organisation_id = :org AND (
      (status = 'running'
        AND coalesce(heartbeat_at, started_at, created_at)
            < now() - make_interval(secs => CAST(:stale AS double precision)))
      OR (status = 'queued'
        AND created_at < now() - make_interval(secs => CAST(:queue AS double precision))))
    """
)


async def lock_org_runs(session: AsyncSession, org: UUID) -> None:
    """Serialise the cap check and insert for one organisation until the transaction ends."""
    await session.execute(
        text("SELECT pg_advisory_xact_lock(hashtextextended(:org, 0))"), {"org": str(org)}
    )


async def insert_run(
    session: AsyncSession,
    *,
    run_id: UUID,
    org: UUID,
    schedule_id: UUID,
    user_id: UUID,
    snapshot: Snapshot,
    options: SolveOptions,
) -> None:
    problem = snapshot.problem.model_copy(update={"options": options})
    await session.execute(
        insert(SolveRun).values(
            id=run_id,
            organisation_id=org,
            schedule_id=schedule_id,
            requested_by=user_id,
            status="queued",
            problem=problem.model_dump(mode="json"),
            problem_hash=snapshot.hash,
            horizon_origin=snapshot.origin,
            timezone=snapshot.timezone,
        )
    )


async def get_run(
    session: AsyncSession, org: UUID, run_id: UUID, *, for_update: bool = False
) -> SolveRun | None:
    query = select(SolveRun).where(SolveRun.organisation_id == org, SolveRun.id == run_id)
    if for_update:
        query = query.with_for_update()
    return await session.scalar(query)


async def list_runs(session: AsyncSession, org: UUID, schedule_id: UUID) -> Sequence[SolveRun]:
    rows = await session.scalars(
        select(SolveRun)
        .where(SolveRun.organisation_id == org, SolveRun.schedule_id == schedule_id)
        .order_by(SolveRun.created_at.desc(), SolveRun.id)
    )
    return rows.all()


async def count_active(session: AsyncSession, org: UUID) -> int:
    return (
        await session.scalar(
            select(func.count())
            .select_from(SolveRun)
            .where(SolveRun.organisation_id == org, SolveRun.status.in_(ACTIVE))
        )
    ) or 0


async def fail_stale_runs(
    session: AsyncSession, org: UUID, stale_after_s: int, queue_timeout_s: int
) -> int:
    result = await session.execute(
        _FAIL_STALE, {"org": org, "stale": stale_after_s, "queue": queue_timeout_s}
    )
    return getattr(result, "rowcount", 0)


async def finish(
    session: AsyncSession,
    run: SolveRun,
    status: str,
    *,
    error: str | None = None,
    conflicts: Iterable[str] = (),
    version_id: UUID | None = None,
) -> None:
    run.status = status
    run.error = error
    run.conflicts = list(conflicts)
    run.version_id = version_id
    run.finished_at = func.now()  # pyright: ignore[reportAttributeAccessIssue]
    await session.flush()
    await session.refresh(run)
