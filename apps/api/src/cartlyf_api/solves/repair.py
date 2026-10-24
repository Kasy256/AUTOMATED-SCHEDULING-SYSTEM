"""The repair problem: today's schedule, the published version as baseline, the past frozen."""

from datetime import datetime
from uuid import UUID

from pydantic import ValidationError
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.errors import Conflict, Unprocessable, field_error
from cartlyf_api.problems.snapshot import Snapshot, build_snapshot
from cartlyf_api.schedules.time_grid import floor_minutes
from cartlyf_api.versions import repository as versions_repo
from cartlyf_engine.domain import Assignment, Pin, Problem, problem_hash


async def repair_snapshot(
    session: AsyncSession, org: UUID, schedule_id: UUID, freeze_before: datetime
) -> tuple[Snapshot, UUID]:
    """The schedule's snapshot with the published version as baseline, every assignment starting
    before `freeze_before` pinned and no other start before it; also returns the baseline id."""
    snapshot = await build_snapshot(session, org, schedule_id)
    problem = snapshot.problem
    if not any(c.template_key == "stability" for c in problem.constraints):
        raise Unprocessable(
            [field_error(("body",), "the schedule needs an enabled stability rule to repair")]
        )
    published = await versions_repo.published_version_id(session, org, schedule_id)
    if published is None:
        raise Conflict("The schedule has no published version to repair")
    activities = {a.id for a in problem.activities}
    baseline: list[Assignment] = []
    frozen: dict[str, Pin] = {}
    placed = await versions_repo.assignments_of(session, org, published)
    for activity_id, (start_at, roles) in placed.items():
        start = floor_minutes(snapshot.origin, start_at)
        if str(activity_id) not in activities or start < 0:
            continue
        resources = {role: tuple(sorted(str(r) for r in ids)) for role, ids in roles.items()}
        baseline.append(Assignment(activity_id=str(activity_id), start=start, resources=resources))
        if start_at < freeze_before:
            frozen[str(activity_id)] = Pin(start=start, resources=resources)
    data = problem.model_dump(mode="json")
    data["baseline"] = [b.model_dump(mode="json") for b in baseline]
    cutoff = floor_minutes(snapshot.origin, freeze_before)
    for activity in data["activities"]:
        if activity["id"] in frozen:
            activity["pinned"] = frozen[activity["id"]].model_dump(mode="json")
            continue
        # Nothing new may be placed in time that has already passed.
        activity["candidate_starts"] = [s for s in activity["candidate_starts"] if s >= cutoff]
        if not activity["candidate_starts"]:
            raise Unprocessable(
                [field_error(("body", "freeze_before"), "some activities have no start after it")]
            )
    try:
        repaired = Problem.model_validate(data)
    except ValidationError:
        raise Unprocessable(
            [
                field_error(
                    ("body", "freeze_before"), "frozen assignments no longer fit the schedule"
                )
            ]
        ) from None
    return Snapshot(repaired, problem_hash(repaired), snapshot.origin, snapshot.timezone), published
