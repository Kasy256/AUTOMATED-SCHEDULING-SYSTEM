from collections.abc import Sequence
from datetime import datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.solves.models import SolveRun
from cartlyf_api.versions.models import Assignment as AssignmentRow
from cartlyf_api.versions.models import AssignmentResource, SolutionVersion
from cartlyf_engine.domain import Assignment, Problem, Score

# Seed 1 keeps schedule keys apart from the per-org solve lock (seed 0).
_LOCK_SCHEDULE = text("SELECT pg_advisory_xact_lock(hashtextextended(:key, 1))")


async def lock_schedule(session: AsyncSession, schedule_id: UUID) -> None:
    """Serialise version numbering and publishing per schedule, until the transaction ends."""
    await session.execute(_LOCK_SCHEDULE, {"key": str(schedule_id)})


async def _next_number(session: AsyncSession, org: UUID, schedule_id: UUID) -> int:
    await lock_schedule(session, schedule_id)
    current = await session.scalar(
        select(func.coalesce(func.max(SolutionVersion.number), 0)).where(
            SolutionVersion.organisation_id == org, SolutionVersion.schedule_id == schedule_id
        )
    )
    return (current or 0) + 1


async def write_version(
    session: AsyncSession,
    *,
    org: UUID,
    schedule_id: UUID,
    run: SolveRun,
    parent_id: UUID | None,
    solver_status: str,
    assignments: Sequence[Assignment],
    score: Score,
    origin: datetime,
    problem: Problem,
    user_id: UUID,
) -> UUID:
    """Insert a draft version and its assignments; the caller has verified `score`."""
    version_id = uuid4()
    report = score.model_dump(mode="json")
    await session.execute(
        insert(SolutionVersion).values(
            id=version_id,
            organisation_id=org,
            schedule_id=schedule_id,
            solve_run_id=run.id,
            parent_version_id=parent_id,
            number=await _next_number(session, org, schedule_id),
            status="draft",
            solver_status=solver_status,
            score=report,
            checker_report=report,
            created_by=user_id,
        )
    )
    if not assignments:
        return version_id
    durations = {a.id: a.duration for a in problem.activities}
    rows: list[dict[str, object]] = []
    resources: list[dict[str, object]] = []
    for placed in assignments:
        start_at = origin + timedelta(minutes=placed.start)
        end_at = start_at + timedelta(minutes=durations[placed.activity_id])
        key: dict[str, object] = {
            "organisation_id": org,
            "version_id": version_id,
            "activity_id": UUID(placed.activity_id),
        }
        rows.append({**key, "start_at": start_at, "end_at": end_at})
        resources += [
            {**key, "role": role, "resource_id": UUID(resource_id)}
            for role, ids in placed.resources.items()
            for resource_id in ids
        ]
    await session.execute(insert(AssignmentRow), rows)
    if resources:
        await session.execute(insert(AssignmentResource), resources)
    return version_id
