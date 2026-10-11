from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import DAY, act, messages, needs, person, place, problem, rule, solve1, solved, who
from strategies import agreement, tiny_problems


def test_RUL_min_load_01_hard_gives_work_to_the_resource() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs())],
        [rule("min", "min_load", period="horizon", min_count=1, scope=Scope(resource_ids=("q",)))],
    )
    assert who(solved(p), "a1") == ("q",)


def test_RUL_min_load_01_hard_infeasible() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs())],
        [rule("min", "min_load", period="horizon", min_count=1)],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("min",))


def test_RUL_min_load_02_checker_explains_the_violation() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs())],
        [rule("min", "min_load", period="horizon", min_count=1)],
    )
    assert messages(p, place("a1", 0, who="q")) == [
        "At least 1 activity per horizon: p has 0 activities in horizon 1"
    ]


def test_RUL_min_load_03_soft_penalty_is_weight_times_shortfall() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs())],
        [rule("min", "min_load", hard=False, weight=2, period="horizon", min_minutes=120)],
    )
    assert check(p, [place("a1", 0, who="p")]).soft_total == 120
    assert solved(p).stats.objective == 120
    per_day = problem(
        [person("p")],
        [act("a1", 60, [0, DAY], needs())],
        [rule("min", "min_load", hard=False, weight=3, period="day", min_count=1)],
    )
    assert solved(per_day).stats.objective == 3


def test_RUL_min_load_05_series_scope() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs(), series="s1"), act("a2", 60, [120], needs(), series="s2")],
        [
            rule(
                "min",
                "min_load",
                period="horizon",
                min_count=1,
                scope=Scope(resource_ids=("p",), series_ids=("s1",)),
            )
        ],
    )
    assert who(solved(p), "a1") == ("p",)


@agreement
@given(tiny_problems(keys=("min_load",)))
def test_RUL_min_load_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
