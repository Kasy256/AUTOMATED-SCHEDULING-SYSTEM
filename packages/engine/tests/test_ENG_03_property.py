from hypothesis import HealthCheck, given, settings

from bruteforce import assert_agree
from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, SolveStatus
from kit import SOLVED, solve1
from strategies import RULE_PARAMS, agreement, tiny_problems


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
        assert solution.stats.objective is not None
        assert score.soft_total <= solution.stats.objective
        if solution.status is SolveStatus.OPTIMAL:
            assert score.soft_total == solution.stats.objective


ALL_RULES = tuple(sorted(RULE_PARAMS))


@agreement
@given(tiny_problems(keys=ALL_RULES, min_rules=1, max_rules=2))
def test_ENG_03_mixed_rules_solver_matches_enumeration(p: Problem) -> None:
    assert_agree(p)


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.too_slow])
@given(tiny_problems(keys=ALL_RULES, min_rules=0, max_rules=3))
def test_ENG_03_every_solution_with_rules_passes_the_checker(p: Problem) -> None:
    solution = solve1(p)
    if solution.status in SOLVED:
        score = check(p, solution.assignments)
        assert score.hard_violations == 0, score.violations
        assert solution.stats.objective is not None
        assert score.soft_total <= solution.stats.objective
        if solution.status is SolveStatus.OPTIMAL:
            assert score.soft_total == solution.stats.objective
