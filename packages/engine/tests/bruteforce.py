"""Exhaustive search over tiny problems: the reference the solver must agree with."""

from itertools import combinations, product
from math import prod

from hypothesis import assume

from cartlyf_engine.checker import check
from cartlyf_engine.domain import Assignment, Problem, SolveStatus
from cartlyf_engine.index import ProblemIndex
from kit import solve1

LIMIT = 1500


def _options(problem: Problem) -> list[list[Assignment]]:
    index = ProblemIndex(problem)
    per_activity: list[list[Assignment]] = []
    for activity in problem.activities:
        roles = [req.role for req in activity.requirements]
        choices = [
            [
                combo
                for k in range(req.count_max + 1)
                for combo in combinations(index.eligible(activity.id, req.role), k)
            ]
            for req in activity.requirements
        ]
        per_activity.append(
            [
                Assignment(
                    activity_id=activity.id,
                    start=start,
                    resources=dict(zip(roles, picked, strict=True)),
                )
                for start in activity.candidate_starts
                for picked in product(*choices)
            ]
        )
    return per_activity


def search_space(problem: Problem) -> int:
    return prod(len(o) for o in _options(problem))


def best_soft_total(problem: Problem) -> int | None:
    best: int | None = None
    for combo in product(*_options(problem)):
        score = check(problem, combo)
        if score.hard_violations == 0 and (best is None or score.soft_total < best):
            best = score.soft_total
    return best


def assert_agree(problem: Problem) -> None:
    assume(search_space(problem) <= LIMIT)
    expected = best_soft_total(problem)
    solution = solve1(problem)
    if expected is None:
        assert solution.status is SolveStatus.INFEASIBLE, solution
        return
    assert solution.status is SolveStatus.OPTIMAL, solution
    assert solution.score.hard_violations == 0, solution.score.violations
    assert solution.stats.objective == expected == solution.score.soft_total
