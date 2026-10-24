from hypothesis import given
from pydantic import JsonValue

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import DAY, act, messages, needs, person, place, problem, rule, solve1, solved, start_of
from strategies import agreement, tiny_problems

LINK: JsonValue = [["s1", "s2"]]


def test_RUL_same_time_01_linked_series_start_together() -> None:
    p = problem(
        [],
        [act("a1", 60, [0, 120], series="s1"), act("a2", 60, [120, 240], series="s2")],
        [rule("link", "same_time", link_groups=LINK)],
    )
    solution = solved(p)
    assert start_of(solution, "a1") == start_of(solution, "a2") == 120


def test_RUL_same_time_01_infeasible_without_a_common_start() -> None:
    p = problem(
        [],
        [act("a1", 60, [0, 120], series="s1"), act("a2", 60, [240], series="s2")],
        [rule("link", "same_time", link_groups=LINK)],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("link",))


def test_RUL_same_time_01_pairs_by_position_in_series() -> None:
    p = problem(
        [],
        [
            act("a1", 60, [0, 120], series="s1"),
            act("a2", 60, [0, DAY], series="s2"),
            act("a3", 60, [DAY, DAY + 120], series="s1"),
            act("a4", 60, [120, DAY + 120], series="s2"),
        ],
        [rule("link", "same_time", link_groups=LINK)],
    )
    solution = solved(p)
    assert (start_of(solution, "a1"), start_of(solution, "a3")) == (0, DAY + 120)


def test_RUL_same_time_02_checker_explains_the_violation() -> None:
    p = problem(
        [],
        [act("a1", 60, [0], series="s1"), act("a2", 60, [120], series="s2")],
        [rule("link", "same_time", link_groups=LINK)],
    )
    assert messages(p, place("a1", 0), place("a2", 120)) == [
        "Linked series start at the same time: a1 starts at 0, a2 at 120"
    ]


def test_RUL_same_time_03_soft_penalty_when_alignment_is_impossible() -> None:
    busy = problem(
        [person("p")],
        [
            act("a1", 60, [0, 120], needs(), series="s1"),
            act("a2", 60, [0, 120], needs(), series="s2"),
        ],
        [rule("link", "same_time", hard=False, weight=2, link_groups=LINK)],
    )
    assert check(busy, [place("a1", 0, who="p"), place("a2", 120, who="p")]).soft_total == 2
    assert solved(busy).stats.objective == 2
    free = problem(
        [],
        [act("a1", 60, [0, 120], series="s1"), act("a2", 60, [0, 120], series="s2")],
        [rule("link", "same_time", hard=False, weight=2, link_groups=LINK)],
    )
    assert solved(free).stats.objective == 0


def test_RUL_same_time_05_scope() -> None:
    p = problem(
        [],
        [act("a1", 60, [0], series="s1"), act("a2", 60, [120], series="s2")],
        [rule("link", "same_time", scope=Scope(series_ids=("s1",)), link_groups=LINK)],
    )
    solved(p)


@agreement
@given(tiny_problems(keys=("same_time",)))
def test_RUL_same_time_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
