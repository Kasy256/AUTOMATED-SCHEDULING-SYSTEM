"""Large-neighbourhood search after the first solution: free a few days or a few resources, fix
the rest to the incumbent, re-solve, keep the result when the checker scores it no worse."""

import random
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from ortools.sat.python import cp_model

from cartlyf_engine.checker import SoftFinding, check_with_findings
from cartlyf_engine.compiler import Compiled
from cartlyf_engine.domain import Assignment, Problem, Score, SolveOptions

# Sub-solves stop on CP-SAT's deterministic time, so the sequence of neighbourhoods and results
# is the same on every machine; wall time only cuts the loop short (ADR 0015).
_SUB_DETERMINISTIC_S = 0.03
_LOOP_DETERMINISTIC_PER_S = 0.5
_STALL_LIMIT = 30
# Sub-models are mostly fixed: a light presolve and no LP relaxation leave more time to search.
_SUB_PARAMETERS = {
    "max_presolve_iterations": 1,
    "cp_model_probing_level": 0,
    "symmetry_level": 0,
    "linearization_level": 0,
}
_MIN_DAYS, _MAX_DAYS = 1, 7
_MIN_RESOURCES, _MAX_RESOURCES = 2, 12
_GUIDED_SHARE = 0.9


@dataclass(frozen=True)
class Incumbent:
    assignments: tuple[Assignment, ...]
    score: Score
    objective: int | None
    findings: tuple[SoftFinding, ...] | None = None


@dataclass
class _Size:
    """Neighbourhood size that grows while sub-solves finish and shrinks when they time out."""

    value: int
    low: int
    high: int

    def update(self, finished: bool) -> None:
        self.value = min(self.high, self.value + 1) if finished else max(self.low, self.value - 1)


def _key(score: Score) -> tuple[int, int]:
    return score.hard_violations, score.soft_total


def improve(
    problem: Problem,
    compiled: Compiled,
    start: Incumbent,
    options: SolveOptions,
    wall_budget_s: float,
    keep_going: Callable[[], bool] = lambda: True,
    attach: Callable[[Callable[[], None] | None], None] = lambda _: None,
    on_improved: Callable[[Incumbent, float], None] = lambda _i, _w: None,
) -> tuple[Incumbent, float]:
    """The best incumbent found and the CP-SAT wall time spent; never worse than `start`.
    Pinned activities are never freed."""
    rng = random.Random(options.seed)
    best = start
    if best.findings is None:
        score, findings = check_with_findings(problem, best.assignments)
        best = Incumbent(best.assignments, score, best.objective, tuple(findings))
    spent_wall = 0.0
    spent_det = 0.0
    det_budget = _LOOP_DETERMINISTIC_PER_S * options.time_limit_s
    days = _Size(_MIN_DAYS + 1, _MIN_DAYS, min(_MAX_DAYS, max(1, len(problem.day_windows))))
    people = _Size(_MIN_RESOURCES + 1, _MIN_RESOURCES, min(_MAX_RESOURCES, len(problem.resources)))
    model = compiled.model
    stalled = 0
    iteration = 0
    while (
        best.score.soft_total > 0
        and stalled < _STALL_LIMIT
        and spent_det < det_budget
        and wall_budget_s - spent_wall > 0.05
        and keep_going()
    ):
        by_days = iteration % 2 == 0 and len(problem.day_windows) > 1
        iteration += 1
        size = days if by_days else people
        guided = None
        if rng.random() < _GUIDED_SHARE:
            within = _window(problem, rng, days.value) if len(problem.day_windows) > 1 else None
            guided = finding_neighbourhood(
                best.assignments, best.findings or (), rng, people.value, within
            )
        free_resources: set[str] = set()
        if guided is not None:
            size = people
            freed, free_resources = guided
        elif by_days:
            freed = _day_window(problem, best.assignments, rng, size.value)
        else:
            freed, free_resources = _resource_subset(problem, best.assignments, rng, size.value)
        saved = _fix(problem, compiled, best.assignments, freed, free_resources)
        solver = cp_model.CpSolver()
        solver.parameters.random_seed = options.seed
        solver.parameters.num_workers = options.num_workers
        solver.parameters.max_deterministic_time = _SUB_DETERMINISTIC_S
        for name, value in _SUB_PARAMETERS.items():
            setattr(solver.parameters, name, value)
        solver.parameters.max_time_in_seconds = wall_budget_s - spent_wall
        attach(solver.stop_search)
        try:
            code = solver.solve(model)
        finally:
            attach(None)
            _restore(model, saved)
        spent_wall += solver.wall_time
        spent_det += solver.response_proto.deterministic_time
        size.update(code == cp_model.OPTIMAL)
        if code not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
            stalled += 1
            continue
        assignments = decode(problem, compiled, solver)
        score, findings = check_with_findings(problem, assignments)
        if _key(score) > _key(best.score):
            stalled += 1
            continue
        improved = _key(score) < _key(best.score)
        stalled = 0 if improved else stalled + 1
        if assignments != best.assignments:
            # The sub-model's objective over-estimates like the full one; the checker is exact.
            best = Incumbent(assignments, score, score.soft_total, tuple(findings))
            if improved:
                on_improved(best, spent_wall)
    return best, spent_wall


def finding_neighbourhood(
    assignments: Sequence[Assignment],
    findings: Sequence[SoftFinding],
    rng: random.Random,
    count: int,
    within: tuple[int, int] | None = None,
) -> tuple[set[str], set[str]] | None:
    """Resources and activities named by soft findings, until `count` resources: a rule is drawn
    uniformly, then one of its findings in proportion to cost. The named activities and every
    activity the resources work (starting `within` the window, if given) are freed, and the
    resources are open to every other activity."""
    # Drawing across rules by cost would let one large, unimprovable rule starve the rest.
    by_rule: dict[str, list[SoftFinding]] = {}
    for f in findings:
        if f.finding.resource_ids or f.finding.activity_ids:
            by_rule.setdefault(f.constraint_id, []).append(f)
    resources: set[str] = set()
    activities: set[str] = set()
    while by_rule and len(resources) < count:
        rule_id = rng.choice(sorted(by_rule))
        named = by_rule[rule_id]
        drawn = rng.choices(range(len(named)), weights=[f.cost for f in named])[0]
        finding = named.pop(drawn).finding
        if not named:
            del by_rule[rule_id]
        resources |= set(finding.resource_ids)
        activities |= set(finding.activity_ids)
    if not resources and not activities:
        return None
    lo, hi = within or (0, max((a.start + 1 for a in assignments), default=0))
    freed = activities | {
        a.activity_id
        for a in assignments
        if lo <= a.start < hi and any(r in resources for ids in a.resources.values() for r in ids)
    }
    return freed, resources


def _window(problem: Problem, rng: random.Random, width: int) -> tuple[int, int]:
    windows = problem.day_windows
    first = rng.randrange(max(1, len(windows) - width + 1))
    return windows[first].start, windows[min(len(windows), first + width) - 1].end


def _day_window(
    problem: Problem, assignments: Sequence[Assignment], rng: random.Random, width: int
) -> set[str]:
    lo, hi = _window(problem, rng, width)
    return {a.activity_id for a in assignments if lo <= a.start < hi}


def _resource_subset(
    problem: Problem, assignments: Sequence[Assignment], rng: random.Random, count: int
) -> tuple[set[str], set[str]]:
    """Some resources of one type, with every activity they now work freed and every other
    activity open to them."""
    by_type: dict[str, list[str]] = {}
    for r in problem.resources:
        by_type.setdefault(r.type_key, []).append(r.id)
    pools = [ids for ids in by_type.values() if len(ids) > 1] or list(by_type.values())
    pool = pools[rng.randrange(len(pools))]
    chosen = set(rng.sample(pool, min(count, len(pool))))
    freed = {
        a.activity_id
        for a in assignments
        if any(r in chosen for ids in a.resources.values() for r in ids)
    }
    return freed, chosen


def _fix(
    problem: Problem,
    compiled: Compiled,
    assignments: Sequence[Assignment],
    freed: set[str],
    free_resources: set[str],
) -> list[tuple[int, int, int]]:
    """Fix every activity outside `freed` to its incumbent start and resources, except picks of
    `free_resources`, by narrowing variable domains in place; hint the incumbent everywhere.
    Returns the narrowed domains to restore. Domains presolve faster than added equalities."""
    model = compiled.model
    model.clear_hints()
    enc, pinned = compiled.encoding, {a.id for a in problem.activities if a.pinned is not None}
    saved: list[tuple[int, int, int]] = []

    def set_to(index: int, value: int) -> None:
        domain = _domain(model, index)
        saved.append((index, domain[0], domain[1]))
        domain[0] = value
        domain[1] = value

    for placed in assignments:
        activity_id = placed.activity_id
        fixed = activity_id in pinned or activity_id not in freed
        for start, lit in enc.starts[activity_id].items():
            value = int(start == placed.start)
            model.add_hint(lit, value)
            if fixed:
                set_to(lit.index, value)
        for role, picks in compiled.picks[activity_id].items():
            for resource_id, lit in picks.items():
                value = int(resource_id in placed.resources.get(role, ()))
                model.add_hint(lit, value)
                if fixed and (activity_id in pinned or resource_id not in free_resources):
                    set_to(lit.index, value)
    return saved


class _Domain(Protocol):
    def __getitem__(self, i: int, /) -> int: ...
    def __setitem__(self, i: int, value: int, /) -> None: ...


def _domain(model: cp_model.CpModel, index: int) -> _Domain:
    # OR-Tools' C++-backed proto ships without type stubs.
    variables = model.proto.variables  # pyright: ignore[reportUnknownMemberType, reportUnknownVariableType]
    return cast(_Domain, variables[index].domain)  # pyright: ignore[reportUnknownMemberType]


def _restore(model: cp_model.CpModel, saved: list[tuple[int, int, int]]) -> None:
    for index, low, high in reversed(saved):
        domain = _domain(model, index)
        domain[0] = low
        domain[1] = high


def decode(
    problem: Problem, compiled: Compiled, solver: cp_model.CpSolver
) -> tuple[Assignment, ...]:
    placed: list[Assignment] = []
    for activity in problem.activities:
        start = next(
            s
            for s, lit in compiled.encoding.starts[activity.id].items()
            if solver.boolean_value(lit)
        )
        roles = {
            role: tuple(r for r, lit in picks.items() if solver.boolean_value(lit))
            for role, picks in compiled.picks[activity.id].items()
        }
        placed.append(Assignment(activity_id=activity.id, start=start, resources=roles))
    return tuple(placed)
