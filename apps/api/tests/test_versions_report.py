from datetime import UTC, date, datetime
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

from cartlyf_api.versions.report import build_report
from cartlyf_engine.domain import Activity, Assignment, Problem, Requirement, Resource, Window

DAY = 1440
L1, L2, R1 = (str(uuid4()) for _ in range(3))
VERSION = uuid4()
ORIGIN = datetime(2027, 1, 11, tzinfo=UTC)  # Monday 00:00 UTC


def problem(
    activities: list[Activity], *, l1_unavailable: tuple[Window, ...] = (), horizon: int = 7 * DAY
) -> Problem:
    return Problem(
        horizon_minutes=horizon,
        day_windows=tuple(Window(start=d * DAY, end=(d + 1) * DAY) for d in range(horizon // DAY)),
        week_windows=(Window(start=0, end=horizon),),
        resources=(
            Resource(id=L1, type_key="lecturer", kind="person", unavailable=l1_unavailable),
            Resource(id=L2, type_key="lecturer", kind="person"),
            Resource(id=R1, type_key="room", kind="space", concurrency=2),
        ),
        activities=tuple(activities),
    )


def act(
    starts: tuple[int, ...], duration: int = 120, requirements: tuple[Requirement, ...] = ()
) -> Activity:
    return Activity(
        id=str(uuid4()), duration=duration, candidate_starts=starts, requirements=requirements
    )


def placed(a: Activity, start: int, **roles: list[str]) -> Assignment:
    return Assignment(
        activity_id=a.id, start=start, resources={k: tuple(v) for k, v in roles.items()}
    )


def report(p: Problem, assignments: list[Assignment], tz: str = "Africa/Kampala"):
    return build_report(VERSION, p, {x.activity_id: x for x in assignments}, ORIGIN, ZoneInfo(tz))


def test_utilisation_is_assigned_over_slot_time_minus_unavailability() -> None:
    a = act((540, 1980))  # Mon 09:00, Tue 09:00 (minutes from Monday 00:00 UTC)
    b = act((540, 1980))
    p = problem([a, b], l1_unavailable=(Window(start=1980, end=2100),))
    out = report(
        p, [placed(a, 540, lecturer=[L1], room=[R1]), placed(b, 1980, lecturer=[L2], room=[R1])]
    )
    by = {u.resource_id: u for u in out.utilisation}
    # slot time = Mon 09-11 + Tue 09-11 = 240; L1 loses Tue 09:00-11:00 → 120 available.
    assert by[UUID(L1)].available_minutes == 120
    assert by[UUID(L1)].assigned_minutes == 120
    assert by[UUID(L1)].ratio == 1.0
    assert by[UUID(L2)].available_minutes == 240 and by[UUID(L2)].ratio == 0.5
    assert by[UUID(R1)].assigned_minutes == 240


def test_overlapping_assignments_on_a_shared_room_count_once() -> None:
    a, b = act((540,)), act((540,))
    p = problem([a, b])
    out = report(p, [placed(a, 540, room=[R1]), placed(b, 540, room=[R1])])
    room = next(u for u in out.utilisation if u.resource_id == UUID(R1))
    assert room.assigned_minutes == 120 and room.available_minutes == 120


def test_load_counts_people_only_and_finds_the_busiest_day() -> None:
    a, b, c = act((540, 1980)), act((540, 1980)), act((690, 1980))
    p = problem([a, b, c])
    out = report(
        p,
        [
            placed(a, 540, lecturer=[L1]),
            placed(b, 1980, lecturer=[L1]),
            placed(c, 690, lecturer=[L1]),
        ],
    )
    load = {x.resource_id: x for x in out.load}
    assert set(load) == {UUID(L1), UUID(L2)}  # the room is not a person
    assert load[UUID(L1)].activities == 3 and load[UUID(L1)].minutes == 360
    assert load[UUID(L1)].busiest_day == date(2027, 1, 11)
    assert load[UUID(L1)].busiest_day_minutes == 240
    assert load[UUID(L2)].activities == 0 and load[UUID(L2)].busiest_day is None


def test_a_resource_in_two_roles_of_one_activity_counts_once() -> None:
    a = act((540,))
    out = report(problem([a]), [placed(a, 540, lecturer=[L1], examiner=[L1])])
    l1 = next(x for x in out.load if x.resource_id == UUID(L1))
    assert l1.activities == 1 and l1.minutes == 120


def test_coverage_gap_when_a_role_gets_fewer_than_its_minimum() -> None:
    soft = Requirement(role="nurse", count_min=2, count_max=3, hard=False, weight=10)
    a = act((540,), requirements=(soft,))
    out = report(problem([a]), [placed(a, 540, nurse=[L1])])
    assert [(g.activity_id, g.role, g.required_min, g.assigned) for g in out.coverage_gaps] == [
        (UUID(a.id), "nurse", 2, 1)
    ]


def test_coverage_gap_starts_at_is_origin_plus_start() -> None:
    soft = Requirement(role="nurse", count_min=2, count_max=2, hard=False, weight=10)
    a = act((540, 1980), requirements=(soft,))
    out = report(problem([a]), [placed(a, 1980, nurse=[])])
    assert [(g.assigned, g.starts_at) for g in out.coverage_gaps] == [
        (0, datetime(2027, 1, 12, 9, 0, tzinfo=UTC))
    ]


def test_fairness_spread_per_type_counts_idle_resources_as_zero() -> None:
    a, b = act((540,)), act((1980,))
    out = report(problem([a, b]), [placed(a, 540, lecturer=[L1]), placed(b, 1980, lecturer=[L1])])
    lect = next(f for f in out.fairness if f.type_key == "lecturer")
    assert (lect.resources, lect.min_minutes, lect.max_minutes, lect.spread) == (2, 0, 240, 240)
    assert lect.mean_minutes == 120.0


def test_busiest_day_uses_local_date_across_dst() -> None:
    # London springs forward on 2027-03-28: 23:30 UTC on the 28th is 00:30 BST on the 29th.
    # Local days: 27th 60, 29th 120. By UTC date it would be a three-way tie (27th wins).
    def at(utc: datetime) -> int:
        return int((utc - ORIGIN).total_seconds() // 60)

    starts = [
        at(datetime(2027, 3, 27, 23, 0, tzinfo=UTC)),
        at(datetime(2027, 3, 28, 23, 30, tzinfo=UTC)),
        at(datetime(2027, 3, 29, 8, 0, tzinfo=UTC)),
    ]
    acts = [act((s,), duration=60) for s in starts]
    p = problem(acts, horizon=90 * DAY)
    out = report(
        p,
        [placed(a, s, lecturer=[L1]) for a, s in zip(acts, starts, strict=True)],
        tz="Europe/London",
    )
    l1 = next(x for x in out.load if x.resource_id == UUID(L1))
    assert l1.busiest_day == date(2027, 3, 29)
    assert l1.busiest_day_minutes == 120


def test_empty_version_reports_zeroes() -> None:
    a = act((540,))
    out = report(problem([a]), [])
    assert out.coverage_gaps == []
    assert all(u.assigned_minutes == 0 for u in out.utilisation)
    assert all(f.spread == 0 for f in out.fairness)
