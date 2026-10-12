from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import (
    DAY,
    act,
    messages,
    needs,
    person,
    place,
    problem,
    rule,
    solve1,
    solved,
    start_of,
    who,
)
from strategies import agreement, tiny_problems


def test_RUL_max_load_01_hard_spreads_work_across_days() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0, DAY], needs()), act("a2", 60, [0, DAY], needs())],
        [rule("cap", "max_load", period="day", max_count=1)],
    )
    solution = solved(p)
    assert {start_of(solution, "a1"), start_of(solution, "a2")} == {0, DAY}


def test_RUL_max_load_01_hard_infeasible_when_the_limit_cannot_hold() -> None:
    p = problem(
        [person("p")],
        [act(f"a{i}", 60, [0, 120, DAY], needs()) for i in range(3)],
        [rule("cap", "max_load", period="day", max_count=1)],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("cap",))


def test_RUL_max_load_01_window_limits_only_that_part_of_the_day() -> None:
    p = problem(
        [person("p")],
        [act(f"a{i}", 60, [0, 120, 800, 920], needs()) for i in range(3)],
        [rule("cap", "max_load", period="day", window="morning", max_count=1)],
    )
    solution = solved(p)
    assert sum(start_of(solution, f"a{i}") < 720 for i in range(3)) == 1


def test_RUL_max_load_02_checker_explains_the_violation() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [120], needs())],
        [rule("cap", "max_load", period="day", max_count=1)],
    )
    assert messages(p, place("a1", 0, who="p"), place("a2", 120, who="p")) == [
        "At most 1 activity per day: p has 2 activities in day 1"
    ]


def test_RUL_max_load_03_soft_penalty_is_weight_times_excess() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [120], needs())],
        [
            rule(
                "cap",
                "max_load",
                hard=False,
                weight=3,
                period="horizon",
                max_count=1,
                max_minutes=60,
            )
        ],
    )
    score = check(p, [place("a1", 0, who="p"), place("a2", 120, who="p")])
    assert score.soft_total == 3 * ((2 - 1) + (120 - 60))
    assert score.terms[0].details == (
        "At most 1 activity and 60 minutes per horizon: p has 2 activities in horizon 1; "
        "At most 1 activity and 60 minutes per horizon: p has 120 minutes in horizon 1"
    )
    assert solved(p).stats.objective == 183


def test_RUL_max_load_03_and_05_solver_moves_work_off_the_resource_in_scope() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs())],
        [
            rule(
                "cap",
                "max_load",
                hard=False,
                weight=5,
                period="day",
                max_count=0,
                scope=Scope(resource_ids=("p",)),
            )
        ],
    )
    assert who(solved(p), "a1") == ("q",)
    assert check(p, [place("a1", 0, who="p")]).soft_total == 5


def test_RUL_max_load_05_series_scope() -> None:
    def build(*series: str) -> Problem:
        return problem(
            [person("p")],
            [act(f"a{i}", 60, [0, 120, 240], needs(), series=s) for i, s in enumerate(series)],
            [rule("cap", "max_load", period="day", max_count=1, scope=Scope(series_ids=("s1",)))],
        )

    solved(build("s1", "s2"))
    assert solve1(build("s1", "s2", "s1")).status is SolveStatus.INFEASIBLE


@agreement
@given(tiny_problems(keys=("max_load",)))
def test_RUL_max_load_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
