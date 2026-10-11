import pytest
from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Activity, Problem, Scope, SolveStatus
from cartlyf_engine.templates.registry import InvalidInstance, validate_instance
from kit import DAY, act, messages, needs, person, place, problem, rule, solve1, solved, start_of
from strategies import agreement, tiny_problems

DAYS = [0, DAY, 2 * DAY]


def _run(n: int, *series: str) -> list[Activity]:
    return [
        act(f"a{i + 1}", 60, DAYS, needs(), series=series[i] if series else None) for i in range(n)
    ]


def test_RUL_max_consecutive_01_hard_breaks_runs() -> None:
    p = problem(
        [person("p")], _run(2), [rule("run", "max_consecutive", unit="days", max=1)], days=3
    )
    solution = solved(p)
    assert sorted(start_of(solution, a) for a in ("a1", "a2")) == [0, 2 * DAY]


def test_RUL_max_consecutive_01_hard_infeasible() -> None:
    p = problem(
        [person("p")], _run(3), [rule("run", "max_consecutive", unit="days", max=1)], days=3
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("run",))


def test_RUL_max_consecutive_01_only_matching_activities_count() -> None:
    p = problem(
        [person("p")],
        _run(3, "s1", "s2", "s1"),
        [
            rule(
                "run", "max_consecutive", unit="days", max=1, activity_filter={"series_ids": ["s1"]}
            )
        ],
        days=3,
    )
    assert start_of(solved(p), "a2") == DAY


def test_RUL_max_consecutive_02_checker_explains_the_violation() -> None:
    p = problem(
        [person("p")], _run(2), [rule("run", "max_consecutive", unit="days", max=1)], days=3
    )
    assert messages(p, place("a1", 0, who="p"), place("a2", DAY, who="p")) == [
        "At most 1 consecutive day worked: p works days 1-2"
    ]


def test_RUL_max_consecutive_03_soft_counts_full_runs() -> None:
    p = problem(
        [person("p")],
        _run(3),
        [rule("run", "max_consecutive", hard=False, weight=2, unit="days", max=1)],
        days=3,
    )
    every_day = [place("a1", 0, who="p"), place("a2", DAY, who="p"), place("a3", 2 * DAY, who="p")]
    assert check(p, every_day).soft_total == 4
    assert solved(p).stats.objective == 4


def test_RUL_max_consecutive_05_scope() -> None:
    p = problem(
        [person("p")],
        _run(3),
        [rule("run", "max_consecutive", unit="days", max=1, scope=Scope(resource_ids=("q",)))],
        days=3,
    )
    solved(p)


def test_unit_activities_is_not_offered_in_v1() -> None:
    with pytest.raises(InvalidInstance):
        validate_instance(
            "max_consecutive", 1, {"unit": "activities", "max": 2}, hard=True, weight=0
        )


@agreement
@given(tiny_problems(keys=("max_consecutive",)))
def test_RUL_max_consecutive_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
