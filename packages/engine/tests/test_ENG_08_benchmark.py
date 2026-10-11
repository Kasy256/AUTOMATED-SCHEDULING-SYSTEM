import time

import pytest

from cartlyf_engine.checker import check
from cartlyf_engine.domain import SolveOptions
from cartlyf_engine.solve import Progress, solve
from cartlyf_engine.synthetic import synthetic_problem
from kit import SOLVED


@pytest.mark.benchmark
def test_ENG_08_synthetic_scale_benchmark() -> None:
    problem = synthetic_problem(seed=1)
    assert (len(problem.activities), len(problem.resources)) == (2000, 300)
    first_solution: list[float] = []

    def on_progress(event: Progress) -> None:
        if event.kind == "solution" and not first_solution and event.wall_time_s is not None:
            first_solution.append(event.wall_time_s)

    started = time.perf_counter()
    solution = solve(
        problem, SolveOptions(time_limit_s=300, seed=1, num_workers=4), on_progress=on_progress
    )
    elapsed = time.perf_counter() - started
    print(
        f"\nENG-08 status={solution.status} objective={solution.stats.objective} "
        f"bound={solution.stats.objective_bound} solver={solution.stats.wall_time_s:.1f}s "
        f"total={elapsed:.1f}s first_solution={first_solution}"
    )
    assert solution.status in SOLVED
    assert check(problem, solution.assignments).hard_violations == 0
    assert elapsed < 600
