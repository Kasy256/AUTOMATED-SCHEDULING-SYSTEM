"""Terse builders and assertions for engine tests."""

from collections.abc import Sequence

from pydantic import JsonValue

from cartlyf_engine.domain import (
    Activity,
    Assignment,
    AttrValue,
    ConstraintInstance,
    Pin,
    Problem,
    Requirement,
    Resource,
    ResourceFilter,
    Scope,
    SolveOptions,
    SolveStatus,
    Window,
)

DAY = 1440
SOLVED = (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


def win(start: int, end: int) -> Window:
    return Window(start=start, end=end)


def person(
    id: str,
    *tags: str,
    attrs: dict[str, AttrValue] | None = None,
    concurrency: int = 1,
    unavailable: Sequence[Window] = (),
    preferred: Sequence[Window] = (),
    avoided: Sequence[Window] = (),
) -> Resource:
    return Resource(
        id=id,
        type_key="person",
        kind="person",
        tags=tags,
        attrs=attrs or {},
        concurrency=concurrency,
        unavailable=tuple(unavailable),
        preferred=tuple(preferred),
        avoided=tuple(avoided),
    )


def room(id: str, capacity: int) -> Resource:
    return Resource(id=id, type_key="room", kind="space", capacity=capacity)


def group(id: str, size: int) -> Resource:
    return Resource(id=id, type_key="group", kind="group", size=size)


def needs(
    role: str = "who",
    type_key: str | None = "person",
    *tags: str,
    count: int = 1,
    count_max: int | None = None,
    fixed: Sequence[str] = (),
    hard: bool = True,
    weight: int = 0,
) -> Requirement:
    return Requirement(
        role=role,
        filter=ResourceFilter(type_key=type_key, tags=tags),
        count_min=count,
        count_max=count_max if count_max is not None else max(count, 1),
        fixed_resource_ids=tuple(fixed),
        hard=hard,
        weight=weight,
    )


def act(
    id: str,
    duration: int,
    starts: Sequence[int],
    *requirements: Requirement,
    series: str | None = None,
    attrs: dict[str, AttrValue] | None = None,
    pin: Pin | None = None,
) -> Activity:
    return Activity(
        id=id,
        series_id=series,
        duration=duration,
        candidate_starts=tuple(starts),
        requirements=requirements,
        attrs=attrs or {},
        pinned=pin,
    )


def rule(
    id: str,
    key: str,
    *,
    hard: bool = True,
    weight: int = 1,
    scope: Scope | None = None,
    **params: JsonValue,
) -> ConstraintInstance:
    return ConstraintInstance(
        id=id,
        template_key=key,
        version=1,
        params=params,
        hard=hard,
        weight=0 if hard else weight,
        scope=scope or Scope(),
    )


def problem(
    resources: Sequence[Resource],
    activities: Sequence[Activity],
    constraints: Sequence[ConstraintInstance] = (),
    *,
    days: int = 2,
) -> Problem:
    """Days of 1440 minutes; one week window; morning = first 720 minutes of each day."""
    return Problem(
        horizon_minutes=days * DAY,
        day_windows=tuple(win(d * DAY, (d + 1) * DAY) for d in range(days)),
        week_windows=(win(0, days * DAY),),
        named_windows={
            "morning": tuple(win(d * DAY, d * DAY + 720) for d in range(days)),
            "afternoon": tuple(win(d * DAY + 720, (d + 1) * DAY) for d in range(days)),
        },
        resources=tuple(resources),
        activities=tuple(activities),
        constraints=tuple(constraints),
    )


def place(activity_id: str, start: int, **roles: str | Sequence[str]) -> Assignment:
    return Assignment(
        activity_id=activity_id,
        start=start,
        resources={k: (v,) if isinstance(v, str) else tuple(v) for k, v in roles.items()},
    )


def options(time_limit_s: int = 10) -> SolveOptions:
    return SolveOptions(time_limit_s=time_limit_s, seed=0, num_workers=1)


def messages(p: Problem, *assignments: Assignment) -> list[str]:
    from cartlyf_engine.checker import check

    return [v.message for v in check(p, assignments).violations]
