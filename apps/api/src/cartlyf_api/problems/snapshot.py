from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import cast
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as activities_repo
from cartlyf_api.activities.models import Activity as ActivityRow
from cartlyf_api.activities.models import Pin as PinRow
from cartlyf_api.activities.models import Requirement as RequirementRow
from cartlyf_api.constraints import repository as constraints_repo
from cartlyf_api.constraints.models import ConstraintInstanceRow
from cartlyf_api.errors import NotFound
from cartlyf_api.fairness.history import history_for
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.resources.calendar import (
    AvailabilityKind,
    DatedException,
    WeeklyRule,
    expand_calendar,
)
from cartlyf_api.resources.models import ResourceType
from cartlyf_api.schedules import repository as schedules_repo
from cartlyf_api.schedules.schemas import DayParts
from cartlyf_api.schedules.time_grid import (
    Interval,
    ceil_minutes,
    day_windows,
    extend_to,
    floor_minutes,
    part_windows,
    week_windows,
)
from cartlyf_engine.domain import (
    Activity,
    AttributePredicate,
    ConstraintInstance,
    Pin,
    Problem,
    Requirement,
    Resource,
    ResourceFilter,
    ResourceKind,
    Scope,
    Window,
    problem_hash,
)


@dataclass(frozen=True)
class Snapshot:
    problem: Problem
    hash: str
    origin: datetime
    timezone: str


Minutes = Callable[[datetime], int]


def _ids(values: Sequence[UUID | str]) -> tuple[str, ...]:
    return tuple(sorted(str(v) for v in values))


def _requirement(row: RequirementRow, types: dict[UUID, ResourceType]) -> Requirement:
    type_key = types[row.resource_type_id].key if row.resource_type_id else None
    return Requirement(
        role=row.role,
        filter=ResourceFilter(
            type_key=type_key,
            tags=tuple(sorted(row.tags)),
            attrs=tuple(AttributePredicate.model_validate(p) for p in row.attr_predicates),
        ),
        count_min=row.count_min,
        count_max=row.count_max,
        fixed_resource_ids=_ids(row.fixed_resource_ids),
        hard=row.hard,
        weight=row.weight,
    )


def _pin(pin: PinRow | None, minutes: Minutes) -> Pin | None:
    if pin is None:
        return None
    return Pin(
        start=None if pin.start_at is None else minutes(pin.start_at),
        resources={role: _ids(ids) for role, ids in pin.resources.items()},
    )


def _activity(
    row: ActivityRow,
    requirements: list[RequirementRow],
    pin: PinRow | None,
    types: dict[UUID, ResourceType],
    minutes: Minutes,
) -> Activity:
    return Activity(
        id=str(row.id),
        series_id=str(row.series_id) if row.series_id else None,
        duration=row.duration_minutes,
        candidate_starts=tuple(sorted(minutes(s) for s in row.candidate_starts)),
        requirements=tuple(_requirement(r, types) for r in requirements),
        pinned=_pin(pin, minutes),
        attrs=row.attrs,
    )


def _constraint(row: ConstraintInstanceRow, types: dict[UUID, ResourceType]) -> ConstraintInstance:
    scope = row.scope
    return ConstraintInstance(
        id=str(row.id),
        template_key=row.template_key,
        version=row.template_version,
        params=row.params,
        hard=row.hard,
        weight=row.weight,
        scope=Scope(
            resource_type_keys=tuple(
                sorted(types[UUID(t)].key for t in scope["resource_type_ids"])
            ),
            tags=tuple(sorted(scope["tags"])),
            attrs=tuple(AttributePredicate.model_validate(p) for p in scope["attrs"]),
            resource_ids=_ids(scope["resource_ids"]),
            series_ids=_ids(scope["series_ids"]),
        ),
    )


async def build_snapshot(
    session: AsyncSession, organisation_id: UUID, schedule_id: UUID
) -> Snapshot:
    """The engine Problem for a schedule, built deterministically from the database."""
    org = organisation_id
    schedule = await schedules_repo.get_schedule(session, org, schedule_id)
    if schedule is None:
        raise NotFound("Unknown schedule")
    base = schedule.horizon()
    origin = base.start
    activities = sorted(
        await activities_repo.list_activities(session, org, schedule_id), key=lambda a: str(a.id)
    )
    # An overnight activity on the last day may end after the schedule; the horizon covers it.
    latest_end = max(
        (max(a.candidate_starts) + timedelta(minutes=a.duration_minutes) for a in activities),
        default=base.end,
    )
    horizon_minutes = max(floor_minutes(origin, base.end), ceil_minutes(origin, latest_end))

    def windows(intervals: list[Interval]) -> tuple[Window, ...]:
        converted = [
            (max(0, floor_minutes(origin, s)), min(horizon_minutes, ceil_minutes(origin, e)))
            for s, e in intervals
        ]
        return tuple(Window(start=s, end=e) for s, e in converted if e > s)

    def minutes(instant: datetime) -> int:
        return floor_minutes(origin, instant)

    types = await resources_repo.types_by_id(session, org)
    rows = sorted(await resources_repo.list_live_resources(session, org), key=lambda r: str(r.id))
    resource_ids = [r.id for r in rows]
    rules = await resources_repo.rules_for(session, org, resource_ids)
    exceptions = await resources_repo.exceptions_for(session, org, resource_ids)
    calendar_horizon = extend_to(base, latest_end)
    resources: list[Resource] = []
    for row in rows:
        calendar = expand_calendar(
            [
                WeeklyRule(cast(AvailabilityKind, r.kind), r.weekday, r.start_minute, r.end_minute)
                for r in rules.get(row.id, [])
            ],
            [
                DatedException(cast(AvailabilityKind, e.kind), e.starts_at, e.ends_at)
                for e in exceptions.get(row.id, [])
            ],
            calendar_horizon,
        )
        rtype = types[row.resource_type_id]
        resources.append(
            Resource(
                id=str(row.id),
                type_key=rtype.key,
                kind=cast(ResourceKind, rtype.kind),
                tags=tuple(sorted(row.tags)),
                attrs=row.attributes,
                capacity=row.capacity,
                size=row.size,
                concurrency=row.concurrency,
                unavailable=windows(calendar.unavailable),
                preferred=windows(calendar.preferred),
                avoided=windows(calendar.avoided),
            )
        )

    requirements = await activities_repo.requirements_for(session, org, [a.id for a in activities])
    pins = await activities_repo.pins_for(session, org, schedule_id)
    constraints = await constraints_repo.enabled_for(session, org, schedule_id)
    parts = DayParts.model_validate(schedule.day_parts).parts
    rule_instances = tuple(
        _constraint(c, types) for c in sorted(constraints, key=lambda c: str(c.id))
    )
    history = await history_for(session, org, schedule, rule_instances, {r.id for r in resources})
    problem = Problem(
        horizon_minutes=horizon_minutes,
        day_windows=windows(day_windows(base)),
        week_windows=windows(week_windows(base)),
        named_windows={
            p.name: windows(part_windows(base, p.start_minute, p.end_minute)) for p in parts
        },
        resources=tuple(resources),
        activities=tuple(
            _activity(a, requirements.get(a.id, []), pins.get(a.id), types, minutes)
            for a in activities
        ),
        constraints=rule_instances,
        history=history,
    )
    return Snapshot(problem, problem_hash(problem), origin, schedule.timezone)
