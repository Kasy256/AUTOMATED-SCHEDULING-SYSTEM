from hypothesis import given

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem
from kit import SOLVED, solve1
from strategies import agreement, tiny_problems


@agreement
@given(tiny_problems())
def test_ENG_03_core_rules_solver_matches_enumeration(p: Problem) -> None:
    assert_agree(p)


@agreement
@given(tiny_problems())
def test_ENG_03_every_returned_solution_passes_the_checker(p: Problem) -> None:
    solution = solve1(p)
    if solution.status in SOLVED:
        score = check(p, solution.assignments)
        assert score.hard_violations == 0, score.violations
        assert score.soft_total == solution.stats.objective
