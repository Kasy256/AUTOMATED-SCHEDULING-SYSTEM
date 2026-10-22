import random
import time
from functools import cache
from pathlib import Path

from ortools.sat.python import cp_model

from cartlyf_engine.checker import check, check_with_findings
from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.construct import construct
from cartlyf_engine.domain import Assignment, Pin, Problem, SolveOptions
from cartlyf_engine.lns import Incumbent, finding_neighbourhood, improve, sub_solver
from cartlyf_engine.solve import solve
from cartlyf_engine.synthetic import synthetic_problem
from kit import DAY, act, needs, person, problem, rule

SHIFTS = {"Day": 420, "Evening": 900, "Night": 1380}
OPTIONS = SolveOptions(time_limit_s=60, seed=0, num_workers=1)
# A 68-variable cut of a roster LNS sub-model, which the default search solves to optimality.
FALSE_INFEASIBLE = Path(__file__).parent / "fixtures/cpsat/false_infeasible.pbtxt"


def rota(people: int = 8, days: int = 7, pin_first_night: str | None = None) -> Problem:
    """Three 8-hour shifts a day for two people each, nights shared fairly; first-fit piles
    nights onto the first people."""
    activities = [
        act(
            f"{slot} {d}",
            480,
            [d * DAY + start],
            needs(count=2, count_max=2, hard=False, weight=100),
            attrs={"slot": slot},
            pin=(
                Pin(resources={"who": (pin_first_night,)})
                if pin_first_night and (slot, d) == ("Night", 0)
                else None
            ),
        )
        for d in range(days)
        for slot, start in SHIFTS.items()
    ]
    rules = [
        rule("rest", "min_rest", minutes=660),
        rule(
            "fair",
            "fairness",
            hard=False,
            weight=10,
            counter="nights",
            activity_filter={"attrs": [{"attr": "slot", "op": "eq", "value": "Night"}]},
            lookback_days=84,
        ),
    ]
    return problem([person(f"p{i:02}") for i in range(people)], activities, rules, days=days + 1)


def improved(p: Problem, start: tuple[Assignment, ...]) -> Incumbent:
    compiled = compile_problem(p)
    result, _ = improve(
        p,
        compiled,
        Incumbent(start, check(p, start), None),
        OPTIONS,
        wall_budget_s=OPTIONS.time_limit_s,
    )
    return result


@cache
def greedy() -> tuple[Problem, tuple[Assignment, ...], Incumbent]:
    p = rota()
    start = construct(p)
    return p, start, improved(p, start)


def test_lns_improves_a_greedy_start() -> None:
    p, start, result = greedy()
    before = check(p, start)
    assert before.hard_violations == 0 and before.soft_total > 0
    assert result.score == check(p, result.assignments)
    assert result.score.hard_violations == 0
    assert result.score.soft_total < before.soft_total


def test_lns_is_deterministic() -> None:
    p, start, result = greedy()
    assert improved(p, start) == result
    first, second = solve(p, OPTIONS), solve(p, OPTIONS)
    assert (first.assignments, first.score) == (second.assignments, second.score)


def test_lns_never_frees_pins() -> None:
    p = rota(pin_first_night="p00")
    start = construct(p)
    [pinned] = [a for a in start if a.activity_id == "Night 0"]
    result = improved(p, start)
    assert result.score.soft_total < check(p, start).soft_total
    assert [a for a in result.assignments if a.activity_id == "Night 0"] == [pinned]


def test_lns_never_worse_than_start() -> None:
    p, _, best = greedy()
    again = improved(p, best.assignments)
    assert (again.score.hard_violations, again.score.soft_total) <= (
        best.score.hard_violations,
        best.score.soft_total,
    )
    solution = solve(p, OPTIONS)
    assert solution.score.soft_total <= check(p, construct(p)).soft_total


def test_lns_charges_its_own_work_to_the_wall_budget() -> None:
    p = synthetic_problem(seed=1, activities=200, resources=60)
    start = construct(p)
    compiled = compile_problem(p)
    options = SolveOptions(time_limit_s=60, seed=0, num_workers=1)
    budget = 3.0
    began = time.perf_counter()
    result, spent = improve(p, compiled, Incumbent(start, check(p, start), None), options, budget)
    elapsed = time.perf_counter() - began
    assert result.score.hard_violations == 0
    assert spent <= budget + 1
    # Fixing, decoding and checking happen outside CP-SAT's clock; they must not overrun.
    assert elapsed <= 1.5 * budget, f"{elapsed:.1f}s for a {budget}s budget"


def test_lns_frees_the_resources_behind_the_costliest_finding() -> None:
    p, start, result = greedy()
    _, findings = check_with_findings(p, start)
    [fair] = [f for f in findings if f.constraint_id == "fair"]
    # Fairness is the only soft rule naming resources, so it is the one every draw lands on.
    named = [f for f in findings if f.finding.resource_ids]
    assert named == [fair]
    neighbourhood = finding_neighbourhood(start, named, random.Random(0), 2)
    assert neighbourhood is not None
    freed, free_resources = neighbourhood
    assert free_resources == set(fair.finding.resource_ids)
    assert freed == {
        a.activity_id for a in start if free_resources & set(a.resources.get("who", ()))
    }
    fair_term = {t.constraint_id: t.penalty for t in result.score.terms}["fair"]
    assert fair_term < fair.cost


def test_lns_sub_solves_never_call_a_feasible_model_infeasible() -> None:
    # Multi-worker CP-SAT 9.15 with cp_model_probing_level=0 calls this model INFEASIBLE in
    # most runs, and can abort the process on the full sub-model (ADR 0015).
    model = cp_model.CpModel()
    model.proto.parse_text_format(FALSE_INFEASIBLE.read_text(encoding="utf-8"))  # pyright: ignore[reportUnknownMemberType]
    for seed in range(40):
        assert sub_solver(seed).solve(model) != cp_model.INFEASIBLE, seed


def test_lns_without_resources_returns_the_start() -> None:
    p = problem([], [act("a", 60, [0], needs(hard=False, weight=5))], days=1)
    start = construct(p)
    compiled = compile_problem(p)
    for seed in range(5):
        options = SolveOptions(time_limit_s=10, seed=seed, num_workers=1)
        result, _ = improve(p, compiled, Incumbent(start, check(p, start), None), options, 10)
        assert result.assignments == start


def test_lns_returns_the_start_untouched_when_cancelled_or_out_of_budget() -> None:
    p, start, _ = greedy()
    compiled = compile_problem(p)
    first = Incumbent(start, check(p, start), None)
    cancelled, spent = improve(p, compiled, first, OPTIONS, 60, keep_going=lambda: False)
    assert cancelled is first and spent == 0
    broke, spent = improve(p, compiled, first, OPTIONS, 0)
    assert broke is first and spent == 0
