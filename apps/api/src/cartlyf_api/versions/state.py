"""A version as the engine sees it: its run's problem snapshot and its assignments in minutes."""

from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.schedules.time_grid import floor_minutes
from cartlyf_api.solves import repository as solves_repo
from cartlyf_api.solves.models import SolveRun
from cartlyf_api.versions import repository
from cartlyf_api.versions.models import SolutionVersion
from cartlyf_engine.domain import Assignment, Problem


def engine_resources(roles: Mapping[str, Iterable[UUID]]) -> dict[str, tuple[str, ...]]:
    return {role: tuple(sorted({str(r) for r in ids})) for role, ids in roles.items()}


@dataclass(frozen=True)
class VersionState:
    version: SolutionVersion
    run: SolveRun
    problem: Problem
    assignments: dict[str, Assignment]


async def load_state(session: AsyncSession, org: UUID, version: SolutionVersion) -> VersionState:
    run = await solves_repo.get_run(session, org, version.solve_run_id)
    assert run is not None, "a version always has its solve run"
    current = await repository.assignments_of(session, org, version.id)
    assignments = {
        str(activity_id): Assignment(
            activity_id=str(activity_id),
            start=floor_minutes(run.horizon_origin, start_at),
            resources=engine_resources(roles),
        )
        for activity_id, (start_at, roles) in current.items()
    }
    return VersionState(version, run, Problem.model_validate(run.problem), assignments)
