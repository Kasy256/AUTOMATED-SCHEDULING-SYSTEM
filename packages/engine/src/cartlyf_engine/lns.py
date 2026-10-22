"""Large-neighbourhood search after the first solution: free a few days or a few resources, fix
the rest to the incumbent, re-solve, keep the result when the checker scores it no worse."""

import random
from collections.abc import Callable, Iterable, Sequence
from dataclasses import dataclass
from typing import Protocol, cast

from ortools.sat.python import cp_model

from cartlyf_engine.checker import SoftFinding, check_with_findings
from cartlyf_engine.compiler import Compiled
from cartlyf_engine.domain import Assignment, Problem, Score, SolveOptions
from cartlyf_engine.index import ProblemIndex

# Sub-solves stop on CP-SAT's deterministic time, so the sequence of neighbourhoods and results
# is the same on every machine; wall time only cuts the loop short (ADR 0015).
_SUB_DETERMINISTIC_S = 0.03
_LOOP_DETERMINISTIC_PER_S = 0.5
_STALL_LIMIT = 30
# Sub-models are mostly fixed: a light presolve and no LP relaxation leave more time to search.
# One worker: with more, CP-SAT 9.15 under probing level 0 calls feasible sub-models INFEASIBLE
# or aborts; with probing on, presolve eats the whole deterministic cap on large models.
_SUB_PARAMETERS = {
    "num_workers": 1,
    "max_presolve_iterations": 1,
    "cp_model_probing_level": 0,
    "symmetry_level": 0,
    "linearization_level": 0,
}
_MIN_DAYS, _MAX_DAYS = 1, 7
_MIN_RESOURCES, _MAX_RESOURCES = 2, 12
_GUIDED_SHARE = 0.9
# The engine reads no clock, so the loop charges its own Python work to the wall budget: per
# literal fixed, opened, hinted or read, and per activity checked. Measured on the slowest
# supported machine (ADR 0015); a faster one only ends the loop a little early.
_LITERAL_S = 1e-5
_CHECK_ACTIVITY_S = 3e-4
_MIN_ITERATION_S = 0.05


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
    """The best incumbent found and the wall time charged for it: CP-SAT's own plus the loop's
    Python work (see `_LITERAL_S`); never worse than `start`. Pinned activities are never
    freed."""
    if wall_budget_s <= _MIN_ITERATION_S or not keep_going():
        return start, 0.0
    rng = random.Random(options.seed)
    index = ProblemIndex(problem)
    best = start
    checked = 0
    if best.findings is None:
        score, findings = check_with_findings(problem, best.assignments, index)
        best = Incumbent(best.assignments, score, best.objective, tuple(findings))
        checked = len(best.assignments)
    det_budget = _LOOP_DETERMINISTIC_PER_S * options.time_limit_s
    days = _Size(_MIN_DAYS + 1, _MIN_DAYS, min(_MAX_DAYS, max(1, len(problem.day_windows))))
    people = _Size(_MIN_RESOURCES + 1, _MIN_RESOURCES, min(_MAX_RESOURCES, len(problem.resources)))
    fixed = _Fixed(problem, compiled, best.assignments)
    fixed.charged += _CHECK_ACTIVITY_S * checked
    spent_det = 0.0
    stalled = 0
    iteration = 0
    try:
        while (
            best.score.soft_total > 0
            and stalled < _STALL_LIMIT
            and spent_det < det_budget
            and wall_budget_s - fixed.charged > _MIN_ITERATION_S
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
            opened = fixed.open(best.assignments, freed, free_resources)
            solver = sub_solver(options.seed)
            solver.parameters.max_time_in_seconds = max(0.01, wall_budget_s - fixed.charged)
            attach(solver.stop_search)
            if not keep_going():
                attach(None)
                break
            try:
                code = solver.solve(compiled.model)
            finally:
                attach(None)
            fixed.charged += solver.wall_time
            spent_det += solver.response_proto.deterministic_time
            size.update(code == cp_model.OPTIMAL)
            found = code in (cp_model.OPTIMAL, cp_model.FEASIBLE)
            assignments = fixed.read(best.assignments, opened, solver) if found else None
            improved = False
            if assignments is not None and assignments != best.assignments:
                score, findings = check_with_findings(problem, assignments, index)
                fixed.charged += _CHECK_ACTIVITY_S * len(assignments)
                if _key(score) <= _key(best.score):
                    improved = _key(score) < _key(best.score)
                    # The sub-model's objective over-estimates like the full one; the checker
                    # is exact.
                    best = Incumbent(assignments, score, score.soft_total, tuple(findings))
            # Close on the incumbent kept, not on a rejected result.
            fixed.close(opened, best.assignments)
            stalled = 0 if improved else stalled + 1
            if improved:
                on_improved(best, fixed.charged)
    finally:
        fixed.release()
    return best, fixed.charged


def sub_solver(seed: int) -> cp_model.CpSolver:
    """A CP-SAT solver configured as every LNS sub-solve is."""
    solver = cp_model.CpSolver()
    solver.parameters.random_seed = seed
    solver.parameters.max_deterministic_time = _SUB_DETERMINISTIC_S
    for name, value in _SUB_PARAMETERS.items():
        setattr(solver.parameters, name, value)
    return solver


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
    if not pools:
        return set(), set()
    pool = pools[rng.randrange(len(pools))]
    chosen = set(rng.sample(pool, min(count, len(pool))))
    freed = {
        a.activity_id
        for a in assignments
        if any(r in chosen for ids in a.resources.values() for r in ids)
    }
    return freed, chosen


@dataclass(frozen=True)
class _Start:
    activity_id: str
    start: int
    lit: cp_model.IntVar

    def value(self, placed: Assignment) -> int:
        return int(placed.start == self.start)


@dataclass(frozen=True)
class _Pick:
    activity_id: str
    role: str
    resource_id: str
    lit: cp_model.IntVar

    def value(self, placed: Assignment) -> int:
        return int(self.resource_id in placed.resources.get(self.role, ()))


_Literal = _Start | _Pick


class _Fixed:
    """Every start and pick literal held at the incumbent's value by narrowing its domain in
    place (domains presolve faster than added equalities). An iteration opens only its
    neighbourhood and closes it again on the next incumbent, so its cost scales with the
    neighbourhood, not the problem. `charged` is the wall time charged so far."""

    def __init__(
        self, problem: Problem, compiled: Compiled, assignments: Sequence[Assignment]
    ) -> None:
        self._model = compiled.model
        self._variables = _variables(compiled.model)
        self._compiled = compiled
        self._pinned = {a.id for a in problem.activities if a.pinned is not None}
        self._by_resource: dict[str, list[_Pick]] = {}
        for activity_id, roles in compiled.picks.items():
            if activity_id in self._pinned:
                continue
            for role, picks in roles.items():
                for resource_id, lit in picks.items():
                    self._by_resource.setdefault(resource_id, []).append(
                        _Pick(activity_id, role, resource_id, lit)
                    )
        # Domain proxies are cached: indexing the proto costs three times a write.
        self._domains: dict[int, _Domain] = {}
        self._original: dict[int, tuple[int, int]] = {}
        self.charged = 0.0
        try:
            for placed in assignments:
                literals = self._literals(placed.activity_id)
                for literal in literals:
                    value = literal.value(placed)
                    domain = self._variables[literal.lit.index].domain
                    self._domains[literal.lit.index] = domain
                    self._original[literal.lit.index] = (domain[0], domain[1])
                    domain[0] = value
                    domain[1] = value
                # Charged for fixing now and for restoring in release().
                self._charge(3 * len(literals))
        except BaseException:
            self.release()
            raise

    def _charge(self, literals: int) -> None:
        self.charged += _LITERAL_S * literals

    def _literals(self, activity_id: str) -> list[_Literal]:
        literals: list[_Literal] = [
            _Start(activity_id, s, lit)
            for s, lit in self._compiled.encoding.starts[activity_id].items()
        ]
        for role, picks in self._compiled.picks[activity_id].items():
            literals += [_Pick(activity_id, role, r, lit) for r, lit in picks.items()]
        return literals

    def open(
        self, assignments: Sequence[Assignment], freed: set[str], free_resources: set[str]
    ) -> list[_Literal]:
        """Open the freed activities and the free resources' picks on every unpinned activity,
        hinting the incumbent on what is open; everything else stays fixed."""
        by_id = {a.activity_id: a for a in assignments}
        opened: list[_Literal] = []
        for activity_id in sorted(freed - self._pinned):
            if activity_id in by_id:
                opened += self._literals(activity_id)
        for resource_id in sorted(free_resources):
            opened += [
                p for p in self._by_resource.get(resource_id, ()) if p.activity_id not in freed
            ]
        for literal in opened:
            low, high = self._original[literal.lit.index]
            domain = self._domains[literal.lit.index]
            domain[0] = low
            domain[1] = high
        self._model.clear_hints()
        # One extend per field: add_hint per literal costs more than the domain writes.
        hint = _hint(self._model)
        hint.vars.extend(literal.lit.index for literal in opened)
        hint.values.extend(literal.value(by_id[literal.activity_id]) for literal in opened)
        self._charge(2 * len(opened))
        return opened

    def close(self, opened: Sequence[_Literal], assignments: Sequence[Assignment]) -> None:
        by_id = {a.activity_id: a for a in assignments}
        for literal in opened:
            value = literal.value(by_id[literal.activity_id])
            domain = self._domains[literal.lit.index]
            domain[0] = value
            domain[1] = value
        self._charge(len(opened))

    def read(
        self,
        assignments: tuple[Assignment, ...],
        opened: Sequence[_Literal],
        solver: cp_model.CpSolver,
    ) -> tuple[Assignment, ...]:
        """The incumbent with the opened literals read back from the solver; every other literal
        was fixed. Changed activities are rebuilt as `decode` builds them."""
        by_id = {a.activity_id: a for a in assignments}
        values: dict[str, list[tuple[_Literal, bool]]] = {}
        changed: set[str] = set()
        for literal in opened:
            on = solver.boolean_value(literal.lit)
            values.setdefault(literal.activity_id, []).append((literal, on))
            if int(on) != literal.value(by_id[literal.activity_id]):
                changed.add(literal.activity_id)
        self._charge(len(opened))
        if not changed:
            return assignments
        result: list[Assignment] = []
        for placed in assignments:
            if placed.activity_id not in changed:
                result.append(placed)
                continue
            start = placed.start
            chosen = {(role, r) for role, ids in placed.resources.items() for r in ids}
            for literal, on in values[placed.activity_id]:
                if isinstance(literal, _Start):
                    start = literal.start if on else start
                elif on:
                    chosen.add((literal.role, literal.resource_id))
                else:
                    chosen.discard((literal.role, literal.resource_id))
            roles = {
                role: tuple(r for r in picks if (role, r) in chosen)
                for role, picks in self._compiled.picks[placed.activity_id].items()
            }
            result.append(Assignment(activity_id=placed.activity_id, start=start, resources=roles))
        return tuple(result)

    def release(self) -> None:
        for index, (low, high) in self._original.items():
            domain = self._domains[index]
            domain[0] = low
            domain[1] = high


class _Domain(Protocol):
    def __getitem__(self, i: int, /) -> int: ...
    def __setitem__(self, i: int, value: int, /) -> None: ...


class _Variable(Protocol):
    @property
    def domain(self) -> _Domain: ...


class _Variables(Protocol):
    def __getitem__(self, i: int, /) -> _Variable: ...


class _Ints(Protocol):
    def extend(self, values: Iterable[int], /) -> None: ...


class _Hint(Protocol):
    @property
    def vars(self) -> _Ints: ...
    @property
    def values(self) -> _Ints: ...


# OR-Tools' C++-backed proto ships without type stubs.
def _variables(model: cp_model.CpModel) -> _Variables:
    return cast(_Variables, model.proto.variables)  # pyright: ignore[reportUnknownMemberType]


def _hint(model: cp_model.CpModel) -> _Hint:
    return cast(_Hint, model.proto.solution_hint)  # pyright: ignore[reportUnknownMemberType]


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
