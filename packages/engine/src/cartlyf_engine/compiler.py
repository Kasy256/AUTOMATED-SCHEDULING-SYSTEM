"""Problem -> CP-SAT model: core rules here, each constraint instance via its template."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from ortools.sat.python import cp_model

from cartlyf_engine.domain import (
    CORE_PIN,
    CORE_UNAVAILABLE,
    Activity,
    Problem,
    Resource,
    ResourceFilter,
    Window,
)
from cartlyf_engine.encoding import Constraint, Encoding, Expr, Rule
from cartlyf_engine.index import ProblemIndex, requirement_pools
from cartlyf_engine.templates.registry import UnsupportedTemplate, get_template

Picks = Mapping[str, Mapping[str, Mapping[str, cp_model.IntVar]]]


@dataclass(frozen=True)
class Compiled:
    model: cp_model.CpModel
    encoding: Encoding
    picks: Picks  # activity -> role -> resource -> literal
    hard: Mapping[int, str]  # enforcing literal index -> hard instance id


class _Core:
    """With `relax` on, each core pool (a requirement minimum per role and filter, a resource's
    unavailability, an activity's pin) is enforced by its own literal so infeasibility can name
    it; otherwise core rules are plain constraints."""

    def __init__(self, model: cp_model.CpModel, relax: bool) -> None:
        self.model = model
        self.relax = relax
        self.literals: dict[str, cp_model.IntVar] = {}

    def literal(self, name: str) -> cp_model.IntVar | None:
        if not self.relax:
            return None
        if name not in self.literals:
            self.literals[name] = self.model.new_bool_var(name)
        return self.literals[name]

    def require(self, constraint: Constraint, name: str) -> None:
        added = (
            constraint
            if isinstance(constraint, cp_model.Constraint)
            else self.model.add(constraint)
        )
        literal = self.literal(name)
        if literal is not None:
            # The OR-Tools stub's catch-all `*args` overload of only_enforce_if is untyped.
            added.only_enforce_if(literal)  # pyright: ignore[reportUnknownMemberType]

    def forbid(self, name: str) -> None:
        literal = self.literal(name)
        if literal is None:
            self.model.add_bool_or([])
        else:
            self.model.add(literal == 0)


def compile_problem(
    problem: Problem, *, assumptions: bool = False, relax_core: bool = False
) -> Compiled:
    """Hard instances are enforced by one literal each: fixed true for a normal solve, or, with
    `assumptions=True`, left as solver assumptions and no objective, to explain infeasibility.
    CP-SAT runs single-threaded with assumptions, so only the explaining solve uses them.
    `relax_core` also puts the core pools behind literals; only `infeasibility.diagnose` uses it."""
    model = cp_model.CpModel()
    core = _Core(model, relax_core)
    pools = requirement_pools(problem)
    index = ProblemIndex(problem)
    starts: dict[str, dict[int, cp_model.IntVar]] = {}
    start: dict[str, cp_model.IntVar] = {}
    picks: dict[str, dict[str, dict[str, cp_model.IntVar]]] = {}
    uses: dict[tuple[str, str], cp_model.IntVar] = {}
    intervals: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)
    shortfalls: list[Expr] = []

    for activity in problem.activities:
        starts[activity.id], start[activity.id] = _place(model, core, activity)
        picks[activity.id] = _staff(model, core, pools, index, activity, shortfalls)
        lits_by_resource: dict[str, list[cp_model.IntVar]] = defaultdict(list)
        for role_picks in picks[activity.id].values():
            for resource_id, lit in role_picks.items():
                lits_by_resource[resource_id].append(lit)
        for resource_id, lits in lits_by_resource.items():
            use = model.new_bool_var(f"use[{activity.id},{resource_id}]")
            model.add(use == sum(lits))  # also stops one resource filling two roles
            uses[activity.id, resource_id] = use
            intervals[resource_id].append(
                model.new_optional_fixed_size_interval_var(
                    start[activity.id], activity.duration, use, ""
                )
            )
    for resource in problem.resources:
        _no_overlap(model, core, resource, intervals[resource.id])

    encoding = Encoding(model, problem, index, starts, start, uses)
    terms: list[Expr] = []
    hard: dict[int, str] = {}
    for instance in problem.constraints:
        spec = get_template(instance.template_key, instance.version)
        if spec.encode is None:
            raise UnsupportedTemplate(instance.template_key)
        enforce = model.new_bool_var(f"hard[{instance.id}]") if instance.hard else None
        rule = Rule(encoding, enforce)
        spec.encode(rule, instance)
        if enforce is not None:
            hard[enforce.index] = instance.id
        else:
            terms.append(instance.weight * sum(rule.amounts))
    terms += shortfalls
    hard |= {literal.index: name for name, literal in core.literals.items()}
    literals = [model.get_bool_var_from_proto_index(i) for i in hard]
    if assumptions:
        model.add_assumptions(literals)
    else:
        for literal in literals:
            model.add(literal == 1)
        model.minimize(sum(terms))
    return Compiled(model, encoding, picks, hard)


def _place(
    model: cp_model.CpModel, core: _Core, activity: Activity
) -> tuple[dict[int, cp_model.IntVar], cp_model.IntVar]:
    lits = {s: model.new_bool_var(f"start[{activity.id}]={s}") for s in activity.candidate_starts}
    model.add_exactly_one(lits.values())
    var = model.new_int_var_from_domain(
        cp_model.Domain.from_values(list(activity.candidate_starts)), f"start[{activity.id}]"
    )
    model.add(var == sum(s * lit for s, lit in lits.items()))
    if activity.pinned is not None and activity.pinned.start is not None:
        core.require(lits[activity.pinned.start] == 1, f"{CORE_PIN}:{activity.id}")
    return lits, var


def _staff(
    model: cp_model.CpModel,
    core: _Core,
    pools: Mapping[tuple[str, ResourceFilter], str],
    index: ProblemIndex,
    activity: Activity,
    shortfalls: list[Expr],
) -> dict[str, dict[str, cp_model.IntVar]]:
    staffed: dict[str, dict[str, cp_model.IntVar]] = {}
    pinned = activity.pinned.resources if activity.pinned is not None else {}
    for req in activity.requirements:
        role = {
            r: model.new_bool_var(f"pick[{activity.id},{req.role},{r}]")
            for r in index.eligible(activity.id, req.role)
        }
        for forced in req.fixed_resource_ids:
            if forced in role:
                model.add(role[forced] == 1)
            else:
                model.add_bool_or([])  # a fixed resource that does not match the filter
        pin = f"{CORE_PIN}:{activity.id}"
        for forced in pinned.get(req.role, ()):
            if forced in role:
                core.require(role[forced] == 1, pin)
            else:
                core.forbid(pin)
        count = sum(role.values())
        model.add(count <= req.count_max)
        if req.hard:
            core.require(count >= req.count_min, pools[req.role, req.filter])
        elif req.count_min > 0:
            short = model.new_int_var(0, req.count_min, "")
            model.add_max_equality(short, [req.count_min - count, 0])
            shortfalls.append(req.weight * short)
        staffed[req.role] = role
    return staffed


def _merged(windows: tuple[Window, ...]) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    for w in sorted(windows, key=lambda w: w.start):
        if merged and w.start <= merged[-1][1]:
            merged[-1] = (merged[-1][0], max(merged[-1][1], w.end))
        else:
            merged.append((w.start, w.end))
    return merged


def _no_overlap(
    model: cp_model.CpModel, core: _Core, resource: Resource, work: list[cp_model.IntervalVar]
) -> None:
    if not work:
        return
    literal = core.literal(f"{CORE_UNAVAILABLE}:{resource.id}") if resource.unavailable else None
    # Overlapping unavailable windows would clash with each other, so merge them first.
    blocked = [
        model.new_fixed_size_interval_var(start, end - start, "")
        if literal is None
        else model.new_optional_fixed_size_interval_var(start, end - start, literal, "")
        for start, end in _merged(resource.unavailable)
    ]
    if len(work) + len(blocked) < 2:
        return
    if resource.concurrency == 1:
        model.add_no_overlap(work + blocked)
    else:
        demands = [1] * len(work) + [resource.concurrency] * len(blocked)
        model.add_cumulative(work + blocked, demands, resource.concurrency)
