"""Hypothesis strategies: tiny problems small enough to enumerate (see bruteforce.py).

Fixed names so rule params can refer to them: persons p1-p2 (tags x/y), room r1, groups g1-g2,
series s1/s2."""

from collections.abc import Callable

from hypothesis import HealthCheck, settings
from hypothesis import strategies as st
from pydantic import JsonValue

from cartlyf_engine.domain import (
    Activity,
    ConstraintInstance,
    Pin,
    Problem,
    Requirement,
    Resource,
    ResourceFilter,
    Scope,
    Window,
)
from cartlyf_engine.templates.registry import get_template
from kit import DAY, problem, win

STARTS = (480, 540, 600, 780, DAY + 480, DAY + 540)
SPOTS = (win(480, 600), win(720, 900), win(DAY + 480, DAY + 600))
ParamsFn = Callable[[st.DrawFn], dict[str, JsonValue]]
RULE_PARAMS: dict[str, ParamsFn] = {}

agreement = settings(
    max_examples=30,
    deadline=None,
    suppress_health_check=[HealthCheck.too_slow, HealthCheck.filter_too_much],
)


def _windows(draw: st.DrawFn) -> tuple[Window, ...]:
    return tuple(draw(st.lists(st.sampled_from(SPOTS), max_size=1)))


def _person(draw: st.DrawFn, n: int) -> Resource:
    return Resource(
        id=f"p{n}",
        type_key="person",
        kind="person",
        tags=tuple(draw(st.lists(st.sampled_from(("x", "y")), unique=True))),
        attrs={"grade": draw(st.integers(1, 2))},
        concurrency=draw(st.integers(1, 2)),
        unavailable=_windows(draw),
        preferred=_windows(draw),
        avoided=_windows(draw),
    )


def _activity(draw: st.DrawFn, n: int, rooms: bool, groups: bool) -> Activity:
    starts = tuple(
        sorted(draw(st.lists(st.sampled_from(STARTS), min_size=1, max_size=2, unique=True)))
    )
    count = draw(st.integers(0, 1))
    hard = draw(st.booleans())
    requirements = [
        Requirement(
            role="who",
            filter=ResourceFilter(
                type_key="person", tags=tuple(draw(st.lists(st.just("x"), max_size=1)))
            ),
            count_min=count,
            count_max=draw(st.integers(max(count, 1), 2)),
            hard=hard,
            weight=0 if hard else draw(st.integers(1, 3)),
        )
    ]
    if rooms and draw(st.booleans()):
        requirements.append(
            Requirement(
                role="room", filter=ResourceFilter(type_key="room"), count_min=1, count_max=1
            )
        )
    if groups and draw(st.booleans()):
        requirements.append(
            Requirement(
                role="group",
                filter=ResourceFilter(type_key="group"),
                count_min=draw(st.integers(0, 1)),
                count_max=1,
            )
        )
    return Activity(
        id=f"a{n}",
        series_id=draw(st.sampled_from(("s1", "s2", None))),
        duration=draw(st.sampled_from((30, 60, 120))),
        candidate_starts=starts,
        requirements=tuple(requirements),
        pinned=Pin(start=draw(st.sampled_from(starts))) if draw(st.integers(0, 4)) == 0 else None,
        attrs={"heads": draw(st.integers(5, 40))},
    )


_SCOPES = st.builds(
    Scope,
    resource_type_keys=st.sampled_from(((), ("person",), ("room",), ("group",))),
    tags=st.sampled_from(((), ("x",))),
    resource_ids=st.sampled_from(((), ("p1",), ("p1", "r1"))),
    series_ids=st.sampled_from(((), ("s1",))),
)


def _instance(draw: st.DrawFn, n: int, key: str) -> ConstraintInstance:
    hard = not get_template(key, 1).soft_only and draw(st.booleans())
    return ConstraintInstance(
        id=f"c{n}",
        template_key=key,
        version=1,
        params=RULE_PARAMS[key](draw),
        scope=draw(_SCOPES),
        hard=hard,
        weight=0 if hard else draw(st.integers(1, 3)),
    )


@st.composite
def tiny_problems(
    draw: st.DrawFn, keys: tuple[str, ...] = (), min_rules: int = 1, max_rules: int = 1
) -> Problem:
    people = [_person(draw, n) for n in range(1, draw(st.integers(1, 2)) + 1)]
    rooms = [Resource(id="r1", type_key="room", kind="space", capacity=draw(st.integers(10, 40)))][
        : draw(st.integers(0, 1))
    ]
    groups = [
        Resource(id=f"g{n}", type_key="group", kind="group", size=draw(st.integers(5, 30)))
        for n in range(1, draw(st.integers(0, 2)) + 1)
    ]
    activities = [
        _activity(draw, n, bool(rooms), bool(groups)) for n in range(1, draw(st.integers(1, 3)) + 1)
    ]
    chosen = (
        draw(st.lists(st.sampled_from(keys), min_size=min_rules, max_size=max_rules))
        if keys
        else []
    )
    constraints = [_instance(draw, n, key) for n, key in enumerate(chosen)]
    return problem([*people, *rooms, *groups], activities, constraints)
