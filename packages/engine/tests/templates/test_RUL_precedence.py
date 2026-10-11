from hypothesis import given
from pydantic import JsonValue

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import act, messages, place, problem, rule, solve1, solved, start_of
from strategies import agreement, tiny_problems

ORDER: JsonValue = [{"before": "s1", "after": "s2"}]


def _pair(gap: int = 0) -> Problem:
    return problem(
        [],
        [act("a1", 60, [0, 120], series="s1"), act("a2", 60, [0, 120], series="s2")],
        [rule("order", "precedence", min_gap=gap, pairs=ORDER)],
    )


def test_RUL_precedence_01_orders_series() -> None:
    solution = solved(_pair())
    assert (start_of(solution, "a1"), start_of(solution, "a2")) == (0, 120)


def test_RUL_precedence_01_gap_makes_it_infeasible() -> None:
    solution = solve1(_pair(gap=61))
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("order",))


def test_RUL_precedence_02_checker_explains_the_violation() -> None:
    assert messages(_pair(), place("a1", 120), place("a2", 0)) == [
        "Series finish at least 0 minutes before their successors start: "
        "a1 ends at 180, a2 starts at 0"
    ]


def test_RUL_precedence_03_soft_counts_pairs_out_of_order() -> None:
    p = problem(
        [],
        [
            act("a1", 60, [0], series="s1"),
            act("a2", 60, [0], series="s1"),
            act("a3", 60, [0], series="s2"),
        ],
        [rule("order", "precedence", hard=False, weight=2, pairs=ORDER)],
    )
    assert check(p, [place("a1", 0), place("a2", 0), place("a3", 0)]).soft_total == 4
    assert solved(p).stats.objective == 4


def test_RUL_precedence_05_scope() -> None:
    p = problem(
        [],
        [act("a1", 60, [120], series="s1"), act("a2", 60, [0], series="s2")],
        [rule("order", "precedence", scope=Scope(series_ids=("s1",)), pairs=ORDER)],
    )
    solved(p)


@agreement
@given(tiny_problems(keys=("precedence",)))
def test_RUL_precedence_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
