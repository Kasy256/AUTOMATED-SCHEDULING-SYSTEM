from pathlib import Path

from cartlyf_engine.domain import Assignment, Problem, Score, Solution, SolveStats, SolveStatus
from tools.metrics import (
    Placement,
    from_legacy_csv,
    from_solution,
    idle_minutes,
    lecturer_load_spread,
    room_fit,
    weekday_spread,
)

LEGACY_CSV = (
    Path(__file__).resolve().parents[1]
    / "packages/engine/tests/fixtures/isbat/legacy/TIMETABLE_TERM1_COMPLETE.csv"
)


def p(groups: tuple[str, ...], lecturer: str, weekday: int, start: int, **kw: int) -> Placement:
    return Placement(
        group_ids=groups,
        lecturer_id=lecturer,
        room_capacity=kw.get("capacity", 40),
        headcount=kw.get("headcount", 30),
        weekday=weekday,
        start_minute=start,
        end_minute=start + kw.get("duration", 120),
    )


def test_idle_minutes_sums_gaps_per_group_and_day() -> None:
    sessions = [p(("A",), "L1", 0, 540), p(("A", "B"), "L2", 0, 840), p(("B",), "L1", 1, 540)]
    assert idle_minutes(sessions) == 180  # A: 11:00 -> 14:00; B has one session per day


def test_lecturer_load_spread() -> None:
    sessions = [p(("A",), "L1", 0, 540), p(("A",), "L1", 1, 540), p(("B",), "L2", 0, 660)]
    low, high, stdev = lecturer_load_spread(sessions)
    assert (low, high) == (1, 2) and round(stdev, 2) == 0.5


def test_room_fit() -> None:
    sessions = [
        p(("A",), "L1", 0, 540, capacity=40, headcount=30),
        p(("B",), "L1", 1, 540, capacity=20, headcount=30),
    ]
    utilisation, over = room_fit(sessions)
    assert round(utilisation, 1) == round((75 + 150) / 2, 1)
    assert over == 1


def test_weekday_spread_is_zero_for_an_even_week() -> None:
    even = [p(("A",), "L1", d, 540) for d in range(5)]
    assert weekday_spread(even) == 0
    assert weekday_spread([p(("A",), "L1", 0, 540), p(("A",), "L1", 0, 840)]) > 0


def test_legacy_csv_rows_sharing_a_session_are_one_placement() -> None:
    sessions = from_legacy_csv(LEGACY_CSV)
    assert len(sessions) == 27  # 24 two-group sessions + 3 single-group
    assert {s.weekday for s in sessions} == {0, 1, 2, 3, 4}
    merged = [s for s in sessions if len(s.group_ids) == 2]
    assert merged and all(s.headcount > 0 for s in merged)


def test_solution_starts_map_to_weekday_and_clock() -> None:
    fixture = Path(__file__).resolve().parents[1] / "packages/engine/tests/fixtures/isbat/v1"
    problem = Problem.model_validate_json((fixture / "term1_problem.json").read_text("utf-8"))
    activity = next(a for a in problem.activities if a.id == "PROG_C W1 #1")
    assignment = Assignment(
        activity_id=activity.id,
        start=1980,  # Tuesday 09:00
        resources={
            "group": ("SG_BCS_126_S1", "SG_BSCAIT_126_S1"),
            "lecturer": ("L001",),
            "room": ("R601",),
        },
    )
    solution = Solution(
        status=SolveStatus.FEASIBLE,
        assignments=(assignment,),
        score=Score(hard_violations=0, soft_total=0),
        stats=SolveStats(wall_time_s=0),
    )
    [placement] = from_solution(problem, solution)
    assert (placement.weekday, placement.start_minute, placement.end_minute) == (1, 540, 660)
    assert (placement.headcount, placement.room_capacity) == (72, 88)
