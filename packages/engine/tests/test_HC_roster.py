"""Healthcare rostering gate on the 40-staff fixture the product pipeline produced (apps/api)."""

import json
import random
import re
from collections.abc import Sequence
from functools import cache
from pathlib import Path

from cartlyf_engine.checker import check
from cartlyf_engine.domain import (
    REQUIREMENTS_TERM,
    Assignment,
    ConstraintInstance,
    PenaltyTerm,
    Pin,
    Problem,
    Resource,
    Solution,
    SolveOptions,
    SolveStatus,
    Window,
)
from cartlyf_engine.solve import solve
from cartlyf_engine.templates import fairness
from cartlyf_engine.templates.scope import in_scope

FIXTURE = Path(__file__).parent / "fixtures/healthcare/v1/roster_problem.json"
ENGINE_SRC = Path(__file__).parents[1] / "src/cartlyf_engine"
SOLVED = (SolveStatus.OPTIMAL, SolveStatus.FEASIBLE)
OPTIONS = SolveOptions(time_limit_s=60, seed=0, num_workers=1)
DAY = 1440
SICK_DAY = 8
REPAIR_DAYS = 3
WORST_SPREAD = 9


def roster() -> Problem:
    return Problem.model_validate(json.loads(FIXTURE.read_text(encoding="utf-8")))


def staff_group(problem: Problem, tag_or_type: str) -> list[Resource]:
    return [r for r in problem.resources if tag_or_type in r.tags or r.type_key == tag_or_type]


def totals(
    problem: Problem, assignments: Sequence[Assignment], instance: ConstraintInstance
) -> dict[str, int]:
    history = (problem.history or {}).get(instance.id, {})
    starts = fairness.counted(problem, instance, assignments)
    return {
        r.id: history.get(r.id, 0) + len(starts.get(r.id, []))
        for r in problem.resources
        if in_scope(r, instance.scope)
    }


def requirements_term(problem: Problem, assignments: Sequence[Assignment]) -> PenaltyTerm:
    [term] = [t for t in check(problem, assignments).terms if t.constraint_id == REQUIREMENTS_TERM]
    return term


def same(a: Assignment, b: Assignment) -> bool:
    def roles(x: Assignment) -> dict[str, list[str]]:
        return {role: sorted(ids) for role, ids in x.resources.items() if ids}

    return a.start == b.start and roles(a) == roles(b)


def overlaps(start: int, end: int, window: Window) -> bool:
    return start < window.end and window.start < end


@cache
def solved() -> Solution:
    return solve(roster(), OPTIONS)


def understaffed() -> Problem:
    problem = roster()
    dropped = {r.id for r in staff_group(problem, "RN")[:8]}
    kept = tuple(r for r in problem.resources if r.id not in dropped)
    return Problem.model_validate({**problem.model_dump(), "resources": kept})


@cache
def solved_understaffed() -> Solution:
    return solve(understaffed(), OPTIONS)


def with_history() -> Problem:
    problem = roster()
    rng = random.Random(8)
    history = {
        c.id: {r.id: rng.randint(0, 3) for r in problem.resources if in_scope(r, c.scope)}
        for c in problem.constraints
        if c.template_key == "fairness"
    }
    return Problem.model_validate({**problem.model_dump(), "history": history})


@cache
def solved_with_history() -> Solution:
    return solve(with_history(), OPTIONS)


def sick_call() -> tuple[Problem, str]:
    """HC-01's roster as baseline, the first RN with a day-8 shift off sick that day, the past
    pinned; returns the repair problem and the sick RN."""
    problem, baseline = roster(), solved().assignments
    day = Window(start=SICK_DAY * DAY, end=(SICK_DAY + 1) * DAY)
    by_id = {a.id: a for a in problem.activities}
    on_sick_day = {
        r
        for a in baseline
        if day.start <= a.start < day.end
        for ids in a.resources.values()
        for r in ids
    }
    sick = next(r.id for r in staff_group(problem, "RN") if r.id in on_sick_day)
    starts = {a.activity_id: a.start for a in baseline}
    pins = {a.activity_id: Pin(start=a.start, resources=a.resources) for a in baseline}
    data = problem.model_dump()
    data["baseline"] = baseline
    data["activities"] = [
        {**a.model_dump(), "pinned": pins[a.id] if starts[a.id] < day.start else None}
        for a in by_id.values()
    ]
    data["resources"] = [
        {**r.model_dump(), "unavailable": (*r.unavailable, day)} if r.id == sick else r
        for r in problem.resources
    ]
    return Problem.model_validate(data), sick


@cache
def solved_sick_call() -> Solution:
    return solve(sick_call()[0], OPTIONS)


def test_HC_01_roster_meets_every_hard_rule() -> None:
    problem, solution = roster(), solved()
    print(f"HC-01 {solution.status} wall {solution.stats.wall_time_s:.1f}s")
    assert solution.status in SOLVED, f"{solution.status}: conflicts {solution.conflicts}"
    assert sorted(a.activity_id for a in solution.assignments) == sorted(
        a.id for a in problem.activities
    )
    score = check(problem, solution.assignments)
    assert score.hard_violations == 0, score.violations[:5]
    term = requirements_term(problem, solution.assignments)
    assert term.penalty == 0, term.details


def test_HC_02_understaffing_is_soft_and_reported_per_shift() -> None:
    problem, solution = understaffed(), solved_understaffed()
    print(f"HC-02 {solution.status} wall {solution.stats.wall_time_s:.1f}s")
    assert solution.status in SOLVED, f"{solution.status}: conflicts {solution.conflicts}"
    assert check(problem, solution.assignments).hard_violations == 0
    assert requirements_term(problem, solution.assignments).penalty > 0
    by_id = {a.id: a for a in problem.activities}
    short = 0
    for assignment in solution.assignments:
        activity = by_id[assignment.activity_id]
        missing = {
            r.role: r.count_min - len(assignment.resources.get(r.role, ()))
            for r in activity.requirements
        }
        if not any(n > 0 for n in missing.values()):
            continue
        short += 1
        # Checked alone, the shift's own shortfall finding is the whole term's text.
        alone = problem.model_copy(update={"activities": (activity,), "constraints": ()})
        details = requirements_term(alone, [assignment]).details
        for role, n in missing.items():
            if n > 0:
                assert f"Role '{role}' of {activity.id} is short by {n}" in details
    assert short > 0


def test_HC_03_fairness_spread_within_bound() -> None:
    problem, solution = with_history(), solved_with_history()
    assert solution.status in SOLVED, f"{solution.status}: conflicts {solution.conflicts}"
    assert check(problem, solution.assignments).hard_violations == 0
    rules = [c for c in problem.constraints if c.template_key == "fairness"]
    spreads = {
        c.id: max(t.values()) - min(t.values())
        for c in rules
        for t in [totals(problem, solution.assignments, c)]
    }
    print(f"HC-03 wall {solution.stats.wall_time_s:.1f}s spreads {spreads}")
    assert len(spreads) == 6
    message = f"measured spreads {spreads}"
    assert max(spreads.values()) <= WORST_SPREAD, message
    # RN nights is the one rule allowed above 2 (known throughput limit, Phase 09 target).
    others = {
        c.id: spreads[c.id]
        for c in rules
        if not (c.scope.tags == ("RN",) and c.params.get("counter") == "nights")
    }
    assert len(others) == 5, message
    assert all(s <= 2 for s in others.values()), message


def test_HC_04_sick_call_repair_is_minimal() -> None:
    (problem, sick), solution = sick_call(), solved_sick_call()
    assert solution.status in SOLVED, f"{solution.status}: conflicts {solution.conflicts}"
    assert check(problem, solution.assignments).hard_violations == 0
    leave = next(r for r in problem.resources if r.id == sick).unavailable[-1]
    durations = {a.id: a.duration for a in problem.activities}
    baseline = {a.activity_id: a for a in problem.baseline or ()}
    lost = [
        a
        for a in baseline.values()
        if any(sick in ids for ids in a.resources.values())
        and overlaps(a.start, a.start + durations[a.activity_id], leave)
    ]
    changed = [a for a in solution.assignments if not same(a, baseline[a.activity_id])]
    print(
        f"HC-04 wall {solution.stats.wall_time_s:.1f}s sick {sick} lost {len(lost)} "
        f"changed {len(changed)}"
    )
    assert lost
    assert len(changed) <= 3 * len(lost)
    window = range(SICK_DAY * DAY, (SICK_DAY + REPAIR_DAYS) * DAY)
    assert all(a.start in window for a in changed), [(a.activity_id, a.start) for a in changed]


def test_HC_05_leave_is_respected() -> None:
    problem = roster()
    on_leave = {r.id: r.unavailable for r in problem.resources if r.unavailable}
    durations = {a.id: a.duration for a in problem.activities}
    assert len(on_leave) == 3
    clashes = [
        (a.activity_id, r)
        for a in solved().assignments
        for ids in a.resources.values()
        for r in ids
        for w in on_leave.get(r, ())
        if overlaps(a.start, a.start + durations[a.activity_id], w)
    ]
    assert clashes == []


def test_HC_engine_has_no_healthcare_code() -> None:
    # Whole words: "Rewards" in the preference template's description is not a ward.
    words = re.compile(r"\b(nurse|midwife|midwives|ward|hospital)s?\b", re.IGNORECASE)
    sources = list(ENGINE_SRC.rglob("*.py"))
    offenders = [str(p) for p in sources if words.search(p.read_text(encoding="utf-8"))]
    assert sources and offenders == []
