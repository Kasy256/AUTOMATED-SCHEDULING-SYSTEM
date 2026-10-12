from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Scope, SolveStatus
from kit import act, messages, needs, person, place, problem, rule, solve1, solved, start_of, who
from strategies import agreement, tiny_problems


def test_RUL_min_rest_01_hard_keeps_a_gap() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, 180], needs())],
        [rule("rest", "min_rest", minutes=60)],
    )
    assert start_of(solved(p), "a2") == 180


def test_RUL_min_rest_01_hard_infeasible() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60, 100], needs())],
        [rule("rest", "min_rest", minutes=60)],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (SolveStatus.INFEASIBLE, ("rest",))


def test_RUL_min_rest_01_overlap_on_a_concurrent_resource_counts() -> None:
    acts = [act("a1", 60, [0], needs()), act("a2", 60, [0], needs())]
    solved(problem([person("p", concurrency=2)], acts))
    with_rest = problem([person("p", concurrency=2)], acts, [rule("rest", "min_rest", minutes=30)])
    assert solve1(with_rest).status is SolveStatus.INFEASIBLE


def test_RUL_min_rest_02_checker_explains_the_violation() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60], needs())],
        [rule("rest", "min_rest", minutes=60)],
    )
    assert messages(p, place("a1", 0, who="p"), place("a2", 60, who="p")) == [
        "At least 60 minutes between a resource's activities: p has 0 minutes between a1 and a2"
    ]


def test_RUL_min_rest_03_soft_counts_close_pairs() -> None:
    acts = [act("a1", 60, [0], needs()), act("a2", 60, [60], needs())]
    alone = problem(
        [person("p")], acts, [rule("rest", "min_rest", hard=False, weight=3, minutes=60)]
    )
    assert check(alone, [place("a1", 0, who="p"), place("a2", 60, who="p")]).soft_total == 3
    assert solved(alone).stats.objective == 3
    helped = problem(
        [person("p"), person("q")],
        acts,
        [rule("rest", "min_rest", hard=False, weight=3, minutes=60)],
    )
    solution = solved(helped)
    assert solution.stats.objective == 0
    assert who(solution, "a1") != who(solution, "a2")


def test_RUL_min_rest_05_scope() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0], needs()), act("a2", 60, [60], needs())],
        [rule("rest", "min_rest", minutes=60, scope=Scope(resource_ids=("q",)))],
    )
    solved(p)


@agreement
@given(tiny_problems(keys=("min_rest",)))
def test_RUL_min_rest_04_encoder_and_checker_agree(p: Problem) -> None:
    assert_agree(p)
