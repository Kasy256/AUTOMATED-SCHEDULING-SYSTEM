"""Problem -> CP-SAT model: core rules here, each constraint instance via its template."""

from collections import defaultdict
from collections.abc import Mapping
from dataclasses import dataclass

from ortools.sat.python import cp_model

from cartlyf_engine.domain import Activity, Problem, Resource, Window
from cartlyf_engine.encoding import Encoding, Expr, Rule
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.registry import UnsupportedTemplate, get_template

Picks = Mapping[str, Mapping[str, Mapping[str, cp_model.IntVar]]]


@dataclass(frozen=True)
class Compiled:
    model: cp_model.CpModel
    encoding: Encoding
    picks: Picks  # activity -> role -> resource -> literal
    assumptions: Mapping[int, str]  # assumption literal index -> hard instance id


def compile_problem(problem: Problem) -> Compiled:
    model = cp_model.CpModel()
    index = ProblemIndex(problem)
    starts: dict[str, dict[int, cp_model.IntVar]] = {}
    start: dict[str, cp_model.IntVar] = {}
    picks: dict[str, dict[str, dict[str, cp_model.IntVar]]] = {}
    uses: dict[tuple[str, str], cp_model.IntVar] = {}
    intervals: dict[str, list[cp_model.IntervalVar]] = defaultdict(list)
    shortfalls: list[Expr] = []

    for activity in problem.activities:
        starts[activity.id], start[activity.id] = _place(model, activity)
        picks[activity.id] = _staff(model, index, activity, shortfalls)
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
        _no_overlap(model, resource, intervals[resource.id])

    encoding = Encoding(model, problem, index, starts, start, uses)
    terms: list[Expr] = []
    assumptions: dict[int, str] = {}
    for instance in problem.constraints:
        spec = get_template(instance.template_key, instance.version)
        if spec.encode is None:
            raise UnsupportedTemplate(instance.template_key)
        enforce = model.new_bool_var(f"hard[{instance.id}]") if instance.hard else None
        rule = Rule(encoding, enforce)
        spec.encode(rule, instance)
        if enforce is not None:
            assumptions[enforce.index] = instance.id
        else:
            terms.append(instance.weight * sum(rule.amounts))
    terms += shortfalls
    if assumptions:
        model.add_assumptions([model.get_bool_var_from_proto_index(i) for i in assumptions])
    model.minimize(sum(terms))
    return Compiled(model, encoding, picks, assumptions)


def _place(
    model: cp_model.CpModel, activity: Activity
) -> tuple[dict[int, cp_model.IntVar], cp_model.IntVar]:
    lits = {s: model.new_bool_var(f"start[{activity.id}]={s}") for s in activity.candidate_starts}
    model.add_exactly_one(lits.values())
    var = model.new_int_var_from_domain(
        cp_model.Domain.from_values(list(activity.candidate_starts)), f"start[{activity.id}]"
    )
    model.add(var == sum(s * lit for s, lit in lits.items()))
    if activity.pinned is not None and activity.pinned.start is not None:
        model.add(lits[activity.pinned.start] == 1)
    return lits, var


def _staff(
    model: cp_model.CpModel, index: ProblemIndex, activity: Activity, shortfalls: list[Expr]
) -> dict[str, dict[str, cp_model.IntVar]]:
    staffed: dict[str, dict[str, cp_model.IntVar]] = {}
    pinned = activity.pinned.resources if activity.pinned is not None else {}
    for req in activity.requirements:
        role = {
            r: model.new_bool_var(f"pick[{activity.id},{req.role},{r}]")
            for r in index.eligible(activity.id, req.role)
        }
        for forced in (*req.fixed_resource_ids, *pinned.get(req.role, ())):
            if forced in role:
                model.add(role[forced] == 1)
            else:
                model.add_bool_or([])  # a forced resource that does not match the filter
        count = sum(role.values())
        model.add(count <= req.count_max)
        if req.hard:
            model.add(count >= req.count_min)
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
    model: cp_model.CpModel, resource: Resource, work: list[cp_model.IntervalVar]
) -> None:
    if not work:
        return
    # Overlapping unavailable windows would clash with each other, so merge them first.
    blocked = [
        model.new_fixed_size_interval_var(start, end - start, "")
        for start, end in _merged(resource.unavailable)
    ]
    if len(work) + len(blocked) < 2:
        return
    if resource.concurrency == 1:
        model.add_no_overlap(work + blocked)
    else:
        demands = [1] * len(work) + [resource.concurrency] * len(blocked)
        model.add_cumulative(work + blocked, demands, resource.concurrency)
