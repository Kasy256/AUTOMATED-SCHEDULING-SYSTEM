"""Seeded synthetic problems for benchmarks, shaped like an education timetable (groups,
lecturers by subject, rooms by type) so ENG-08 measures what ISBAT-like data produces."""

import random
from collections import defaultdict

from cartlyf_engine.domain import (
    Activity,
    AttributePredicate,
    ConstraintInstance,
    Problem,
    Requirement,
    Resource,
    ResourceFilter,
    Scope,
    Window,
)

DAY = 1440
SLOT_STARTS = (480, 580, 680, 800, 900, 1000)
SLOT_MINUTES = 90
SESSIONS_PER_SERIES = 4


def synthetic_problem(
    seed: int,
    *,
    activities: int = 2000,
    resources: int = 300,
    days: int = 10,
    subjects: int = 30,
    room_types: int = 4,
) -> Problem:
    rng = random.Random(seed)
    n_groups, n_rooms = resources // 3, resources // 4
    n_lecturers = resources - n_groups - n_rooms
    groups = [
        Resource(id=f"g{i}", type_key="group", kind="group", size=rng.randint(15, 40))
        for i in range(n_groups)
    ]
    rooms = [
        Resource(
            id=f"r{i}",
            type_key="room",
            kind="space",
            capacity=rng.randint(40, 80),
            attrs={"room_type": f"t{i % room_types}"},
        )
        for i in range(n_rooms)
    ]
    lecturers = [
        Resource(
            id=f"l{i}",
            type_key="lecturer",
            kind="person",
            tags=tuple(sorted({f"s{(i + 7 * k) % subjects}" for k in range(3)})),
        )
        for i in range(n_lecturers)
    ]
    starts = tuple(d * DAY + s for d in range(days) for s in SLOT_STARTS)
    taken: dict[int, set[int]] = defaultdict(set)
    work: list[Activity] = []
    turn = 0
    while len(work) < activities:
        g = turn % n_groups
        turn += 1
        subject = rng.choice([s for s in range(subjects) if s not in taken[g]])
        taken[g].add(subject)
        series = f"g{g}-s{subject}"
        room_type = f"t{rng.randrange(room_types)}"
        requirements = (
            Requirement(
                role="group",
                filter=ResourceFilter(type_key="group"),
                count_min=1,
                count_max=1,
                fixed_resource_ids=(f"g{g}",),
            ),
            Requirement(
                role="lecturer",
                filter=ResourceFilter(type_key="lecturer", tags=(f"s{subject}",)),
                count_min=1,
                count_max=1,
            ),
            Requirement(
                role="room",
                filter=ResourceFilter(
                    type_key="room",
                    attrs=(AttributePredicate(attr="room_type", op="eq", value=room_type),),
                ),
                count_min=1,
                count_max=1,
            ),
        )
        for k in range(min(SESSIONS_PER_SERIES, activities - len(work))):
            work.append(
                Activity(
                    id=f"{series}-{k}",
                    series_id=series,
                    duration=SLOT_MINUTES,
                    candidate_starts=starts,
                    requirements=requirements,
                )
            )

    def rule(
        id: str, key: str, params: dict[str, object], scope: Scope, weight: int = 0
    ) -> ConstraintInstance:
        return ConstraintInstance.model_validate(
            {
                "id": id,
                "template_key": key,
                "version": 1,
                "params": params,
                "scope": scope,
                "hard": weight == 0,
                "weight": weight,
            }
        )

    lecturer_scope, group_scope = (
        Scope(resource_type_keys=("lecturer",)),
        Scope(resource_type_keys=("group",)),
    )
    horizon = days * DAY
    return Problem(
        horizon_minutes=horizon,
        day_windows=tuple(Window(start=d * DAY, end=(d + 1) * DAY) for d in range(days)),
        week_windows=tuple(
            Window(start=w, end=min(w + 7 * DAY, horizon)) for w in range(0, horizon, 7 * DAY)
        ),
        named_windows={
            "morning": tuple(Window(start=d * DAY, end=d * DAY + 720) for d in range(days)),
            "afternoon": tuple(Window(start=d * DAY + 720, end=(d + 1) * DAY) for d in range(days)),
        },
        resources=(*groups, *rooms, *lecturers),
        activities=tuple(work),
        constraints=(
            rule("lecturer-day", "max_load", {"period": "day", "max_count": 3}, lecturer_scope),
            rule("series-spread", "spread", {"max_per_day": 1}, Scope()),
            rule("room-fit", "capacity_fit", {}, Scope()),
            rule("group-gaps", "minimize_gaps", {"per_minutes": 60}, group_scope, weight=1),
            rule("lecturer-balance", "balance", {"measure": "count"}, lecturer_scope, weight=1),
        ),
    )
