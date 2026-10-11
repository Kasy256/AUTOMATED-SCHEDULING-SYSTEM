from cartlyf_engine.domain import SolveOptions, problem_hash
from cartlyf_engine.precheck import precheck
from cartlyf_engine.solve import solve
from cartlyf_engine.synthetic import synthetic_problem
from kit import SOLVED


def test_synthetic_problem_is_seeded_and_sized() -> None:
    first = synthetic_problem(seed=1, activities=200, resources=60, days=5)
    assert (len(first.activities), len(first.resources)) == (200, 60)
    assert problem_hash(first) == problem_hash(
        synthetic_problem(seed=1, activities=200, resources=60, days=5)
    )
    assert problem_hash(first) != problem_hash(
        synthetic_problem(seed=2, activities=200, resources=60, days=5)
    )


def test_small_synthetic_problem_passes_precheck_and_solves() -> None:
    p = synthetic_problem(seed=1, activities=100, resources=45, days=5)
    assert precheck(p) == []
    solution = solve(p, SolveOptions(time_limit_s=30, seed=0, num_workers=1))
    assert solution.status in SOLVED
    assert solution.score.hard_violations == 0
