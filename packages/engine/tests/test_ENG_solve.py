import random
import threading
import time
from collections.abc import Sequence
from itertools import pairwise

import pytest

from cartlyf_engine.checker import check
from cartlyf_engine.domain import (
    Assignment,
    Problem,
    Resource,
    Scope,
    Score,
    SolveOptions,
    SolveStatus,
    Violation,
)
from cartlyf_engine.solve import CancelToken, Progress, solve
from cartlyf_engine.synthetic import synthetic_problem
from kit import DAY, SOLVED, act, needs, options, person, problem, rule, solve1, solved, win


def _busy() -> Problem:
    return synthetic_problem(seed=2, activities=400, resources=90, days=5)


def _improvable(n_activities: int = 60, n_people: int = 8) -> Problem:
    """One-person activities with soft balance and avoided times: several improving solutions."""
    rng = random.Random(0)
    slots = [d * DAY + 480 + 60 * k for d in range(2) for k in range(10)]
    people: list[Resource] = []
    for i in range(n_people):
        t = rng.randrange(2) * DAY + 480 + 60 * rng.randrange(9)
        people.append(person(f"p{i}", avoided=[win(t, t + 120)]))
    activities = [
        act(f"a{i}", 60, sorted(rng.sample(slots, 6)), needs()) for i in range(n_activities)
    ]
    rules = [
        rule("bal", "balance", hard=False, weight=3, measure="count"),
        rule("pref", "preference", hard=False, weight=2, source="calendar"),
    ]
    return problem(people, activities, rules)


def test_ENG_01_known_optimum_avoided_time() -> None:
    p = problem(
        [person("p", avoided=[win(0, 60)])],
        [act("a1", 60, [0, 60], needs()), act("a2", 60, [0, 60], needs())],
        [rule("pref", "preference", hard=False, weight=3, source="calendar")],
    )
    solution = solved(p)
    assert (solution.status, solution.stats.objective) == (SolveStatus.OPTIMAL, 3)


def test_ENG_01_known_optimum_no_gaps() -> None:
    p = problem(
        [person("p")],
        [act(f"a{i}", 60, [0, 60, 120, 180, 240], needs()) for i in range(3)],
        [rule("gaps", "minimize_gaps", hard=False, weight=1, per_minutes=60)],
    )
    solution = solved(p)
    assert (solution.status, solution.stats.objective) == (SolveStatus.OPTIMAL, 0)


def test_ENG_01_known_optimum_understaffed() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs(count=3, count_max=3, hard=False, weight=5))],
    )
    solution = solved(p)
    assert (solution.status, solution.stats.objective) == (SolveStatus.OPTIMAL, 5)


def test_ENG_04_infeasible_names_the_conflicting_instance() -> None:
    p = problem(
        [person("p")],
        [act("a1", 60, [0, 120], needs()), act("a2", 60, [0, 120], needs())],
        [
            rule("one-a-day", "max_load", period="day", max_count=1),
            rule("rest", "min_rest", minutes=30),
        ],
    )
    solution = solve1(p)
    assert solution.status is SolveStatus.INFEASIBLE
    assert solution.conflicts == ("one-a-day",)
    assert (solution.assignments, solution.score.hard_violations) == ((), 0)


def test_ENG_04_conflicts_name_every_instance_in_the_clash() -> None:
    only_p = Scope(resource_ids=("p",))
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0, 120], needs()), act("a2", 60, [0, 120], needs())],
        [
            rule("one-a-day", "max_load", period="day", max_count=1, scope=only_p),
            rule("at-least-two", "min_load", period="horizon", min_count=2, scope=only_p),
        ],
    )
    solution = solve1(p)
    assert (solution.status, solution.conflicts) == (
        SolveStatus.INFEASIBLE,
        ("at-least-two", "one-a-day"),
    )


def test_ENG_05_one_term_per_soft_instance_and_totals_match() -> None:
    p = problem(
        [person("p", preferred=[win(0, 720)]), person("q")],
        [act("a1", 60, [0, 800], needs()), act("a2", 60, [0, 800], needs())],
        [
            rule("pref", "preference", hard=False, weight=2, source="calendar"),
            rule("bal", "balance", hard=False, weight=3, measure="count"),
            rule("cap", "max_load", period="day", max_count=2),
            rule(
                "nobody",
                "min_rest",
                hard=False,
                weight=1,
                minutes=30,
                scope=Scope(resource_ids=("ghost",)),
            ),
        ],
    )
    solution = solved(p)
    assert [t.constraint_id for t in solution.score.terms] == ["pref", "bal", "nobody"]
    assert solution.score.terms[2].penalty == 0
    assert sum(t.penalty for t in solution.score.terms) == solution.stats.objective


def test_ENG_06_time_limit_respected_with_best_so_far() -> None:
    # CP-SAT checks the limit coarsely during presolve, so a 10% margin needs a non-tiny limit.
    solution = solve(_busy(), SolveOptions(time_limit_s=10, seed=0, num_workers=1))
    assert solution.stats.wall_time_s <= 10 * 1.1
    assert solution.status in (SolveStatus.FEASIBLE, SolveStatus.UNKNOWN)
    if solution.status is SolveStatus.FEASIBLE:
        assert check(_busy(), solution.assignments).hard_violations == 0


def test_ENG_07_progress_on_improving_solutions_and_bounds() -> None:
    events: list[Progress] = []
    solution = solve(
        _improvable(),
        SolveOptions(time_limit_s=10, seed=0, num_workers=1),
        on_progress=events.append,
    )
    found = [e.objective for e in events if e.kind == "solution" and e.objective is not None]
    assert found
    assert all(later <= earlier for earlier, later in pairwise(found))
    assert any(e.kind in ("bound", "log") for e in events)
    if solution.status in SOLVED:
        assert found[-1] == solution.stats.objective


def test_cancel_from_another_thread_stops_the_search() -> None:
    token = CancelToken()
    timer = threading.Timer(1.0, token.cancel)
    timer.start()
    started = time.perf_counter()
    solution = solve(_busy(), SolveOptions(time_limit_s=60, seed=0, num_workers=1), cancel=token)
    timer.cancel()
    assert solution.status in (SolveStatus.FEASIBLE, SolveStatus.UNKNOWN)
    assert solution.stats.wall_time_s < 5
    assert time.perf_counter() - started < 30


def test_cancel_before_solving_returns_unknown_at_once() -> None:
    token = CancelToken()
    token.cancel()
    solution = solve(problem([person("p")], [act("a1", 60, [0], needs())]), cancel=token)
    assert (solution.status, solution.stats.wall_time_s) == (SolveStatus.UNKNOWN, 0)


def test_construction_is_returned_when_search_is_stopped_at_once() -> None:
    token = CancelToken()
    events: list[Progress] = []

    def on_progress(event: Progress) -> None:
        events.append(event)
        if event.kind == "constructed":
            token.cancel()

    p = _improvable()
    solution = solve(p, options(), on_progress=on_progress, cancel=token)
    assert solution.status is SolveStatus.FEASIBLE
    assert solution.score == check(p, solution.assignments)
    assert solution.score.hard_violations == 0
    assert solution.stats.objective == solution.score.soft_total
    assert [e.kind for e in events if e.kind == "constructed"] == ["constructed"]


def test_zero_penalty_construction_is_optimal_without_search() -> None:
    # Penalties are never negative, so a verified start costing 0 needs no proof from CP-SAT.
    token = CancelToken()

    def on_progress(event: Progress) -> None:
        if event.kind == "constructed":
            token.cancel()

    p = problem([person("p")], [act("a1", 60, [0, 60], needs())])
    solution = solve(p, options(), on_progress=on_progress, cancel=token)
    assert solution.status is SolveStatus.OPTIMAL
    assert solution.score.soft_total == solution.stats.objective == 0


def test_unverified_construction_is_not_returned() -> None:
    p = problem(
        [person("p"), person("q")],
        [act("a1", 60, [0], needs()), act("a2", 60, [120], needs())],
        [rule("min", "min_load", period="horizon", min_count=2, scope=Scope(resource_ids=("q",)))],
    )
    solution = solved(p)
    assert all(a.resources["who"] == ("q",) for a in solution.assignments)


def test_a_search_result_with_hard_violations_never_beats_a_verified_construction(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import cartlyf_engine.solve as solve_module

    calls: list[int] = []

    def disagreeing_check(p: Problem, assignments: Sequence[Assignment]) -> Score:
        calls.append(1)
        score = check(p, assignments)
        if len(calls) == 1:
            return score
        broken = Violation(constraint_id="core:overlap", message="simulated solver bug")
        return score.model_copy(update={"hard_violations": 1, "violations": (broken,)})

    monkeypatch.setattr(solve_module, "check", disagreeing_check)
    solution = solve(_improvable(), options())
    assert solution.status is SolveStatus.FEASIBLE
    assert solution.score.hard_violations == 0
    assert solution.stats.objective == solution.score.soft_total
