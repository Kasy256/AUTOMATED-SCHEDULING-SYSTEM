from cartlyf_engine.checker import check
from cartlyf_engine.construct import construct
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


def test_generated_problems_are_feasible() -> None:
    # First-fit may leave a few activities for CP-SAT (400 x 90 verified FEASIBLE by a hinted solve,
    # 2026-10-12); every placement it makes must be clean.
    for size, share in (((100, 45, 5), 1.0), ((400, 90, 5), 0.98)):
        p = synthetic_problem(seed=2, activities=size[0], resources=size[1], days=size[2])
        plan = construct(p)
        assert len(plan) >= share * len(p.activities), size
        score = check(p, plan)
        assert all(v.constraint_id == "core:placement" for v in score.violations), size
