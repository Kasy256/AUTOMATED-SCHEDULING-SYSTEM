"""ISBAT Term 1 benchmark on the fixture the product pipeline produced (apps/api EDU tests)."""

import json
from functools import cache
from pathlib import Path

import pytest

from cartlyf_engine.checker import check
from cartlyf_engine.domain import Problem, Solution, SolveOptions, SolveStatus
from cartlyf_engine.solve import solve

FIXTURE = Path(__file__).parent / "fixtures/isbat/v1/term1_problem.json"
ENGINE_SRC = Path(__file__).parents[1] / "src/cartlyf_engine"
SOLVED = (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)


def term1() -> Problem:
    return Problem.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


@cache
def solved() -> Solution:
    # Feasibility is the gate here; EDU-05 times the 4-worker solve.
    return solve(term1(), SolveOptions(time_limit_s=20, seed=0, num_workers=1))


def test_EDU_03_term1_places_every_session_with_zero_hard_violations() -> None:
    problem, solution = term1(), solved()
    assert solution.status in SOLVED, f"{solution.status}: conflicts {solution.conflicts}"
    assert sorted(a.activity_id for a in solution.assignments) == sorted(
        a.id for a in problem.activities
    )
    assert check(problem, solution.assignments).hard_violations == 0
    assert solution.score.hard_violations == 0


def test_EDU_04_merged_groups_attend_together() -> None:
    by_id = {a.id: a for a in term1().activities}
    for assignment in solved().assignments:
        [group] = [r for r in by_id[assignment.activity_id].requirements if r.role == "group"]
        assert sorted(assignment.resources["group"]) == sorted(group.fixed_resource_ids)


def test_EDU_02_engine_has_no_education_code() -> None:
    words = ("isbat", "education", "lecturer", "student")
    # synthetic.py only generates benchmark data shaped like a timetable; it holds no rules.
    sources = [p for p in ENGINE_SRC.rglob("*.py") if p.name != "synthetic.py"]
    offenders = [
        str(p) for p in sources if any(w in p.read_text(encoding="utf-8").lower() for w in words)
    ]
    assert sources and offenders == []


@pytest.mark.benchmark
def test_EDU_05_term1_under_60s_on_4_workers() -> None:
    solution = solve(term1(), SolveOptions(time_limit_s=60, seed=0, num_workers=4))
    print(
        f"EDU-05 status {solution.status} wall {solution.stats.wall_time_s:.1f}s "
        f"soft {solution.score.soft_total} hard {solution.score.hard_violations}"
    )
    assert solution.status in SOLVED
    assert solution.score.hard_violations == 0
    assert solution.stats.wall_time_s < 60
