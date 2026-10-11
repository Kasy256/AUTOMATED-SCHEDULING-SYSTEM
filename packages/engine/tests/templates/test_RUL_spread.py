from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import DAY, act, messages, place, problem, rule, solve1, solved, start_of
from strategies import agreement, tiny_problems


def test_RUL_spread_01_hard_one_per_day() -> None:
    p = problem(
        [],
        [act(f"a{i}", 60, [0, 120, DAY], series="s1") for i in (1, 2)],
        [rule("spread", "spread", max_per_day=1)],
    )
    solution = solved(p)
    assert {start_of(solution, "a1") // DAY, start_of(solution, "a2") // DAY} == {0, 1}


def test_RUL_spread_01_hard_infeasible() -> None:
    p = problem(
        [],
        [act(f"a{i}", 60, [0, DAY], series="s1") for i in (1, 2, 3)],
        [rule("spread", "spread", max_per_day=1)],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("spread",))


def test_RUL_spread_01_min_days_apart() -> None:
    p = problem(
        [],
        [act(f"a{i}", 60, [0, DAY, 2 * DAY], series="s1") for i in (1, 2)],
        [rule("spread", "spread", min_days_apart=2)],
        days=3,
    )
    solution = solved(p)
    assert sorted(start_of(solution, a) for a in ("a1", "a2")) == [0, 2 * DAY]


def test_RUL_spread_02_checker_explains_the_violation() -> None:
    per_day = problem(
        [],
        [act(f"a{i}", 60, [0, 120], series="s1") for i in (1, 2)],
        [rule("spread", "spread", max_per_day=1)],
    )
    assert messages(per_day, place("a1", 0), place("a2", 120)) == [
        "Activities of a series: at most 1 per day: series s1 has 2 activities on day 1"
    ]
    apart = problem(
        [],
        [act(f"a{i}", 60, [0, DAY], series="s1") for i in (1, 2)],
        [rule("spread", "spread", min_days_apart=2)],
        days=3,
    )
    assert messages(apart, place("a1", 0), place("a2", DAY)) == [
        "Activities of a series: at least 2 days apart: series s1 has 2 activities within days 1-2"
    ]


def test_RUL_spread_03_soft_penalty_and_preference() -> None:
    crowded = problem(
        [],
        [act(f"a{i}", 60, [0, 120, 240], series="s1") for i in (1, 2, 3)],
        [rule("spread", "spread", hard=False, weight=4, max_per_day=1)],
    )
    assert check(crowded, [place("a1", 0), place("a2", 120), place("a3", 240)]).soft_total == 8
    assert solved(crowded).stats.objective == 8
    roomy = problem(
        [],
        [act(f"a{i}", 60, [0, DAY], series="s1") for i in (1, 2)],
        [rule("spread", "spread", hard=False, weight=4, max_per_day=1)],
    )
    assert solved(roomy).stats.objective == 0


def test_RUL_spread_05_scope() -> None:
    p = problem(
        [],
        [
            act("a1", 60, [0, 120], series="s2"),
            act("a2", 60, [0, 120], series="s2"),
            act("a3", 60, [0, DAY], series="s1"),
            act("a4", 60, [0, DAY], series="s1"),
        ],
        [rule("spread", "spread", max_per_day=1, scope=Scope(series_ids=("s1",)))],
    )
    solved(p)


@agreement
@given(tiny_problems(keys=("spread",)))
def test_RUL_spread_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
