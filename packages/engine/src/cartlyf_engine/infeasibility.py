"""Infeasibility report: the rules and core pools that conflict, and which single relaxation
removes the conflict (tested with a short solve each)."""

from collections.abc import Sequence
from typing import Literal

from ortools.sat.python import cp_model

from cartlyf_engine.compiler import compile_problem
from cartlyf_engine.domain import (
    CORE_PIN,
    CORE_UNAVAILABLE,
    ConstraintInstance,
    Frozen,
    Id,
    Problem,
    ResourceFilter,
)
from cartlyf_engine.index import requirement_pools
from cartlyf_engine.solve import CancelToken
from cartlyf_engine.templates.registry import describe, get_template

ConflictKind = Literal["rule", "requirement", "unavailable", "pin"]
RelaxationKind = Literal["switch_to_soft", "change_param", "add_resource", "free_resource", "unpin"]


class Conflict(Frozen):
    id: Id
    kind: ConflictKind
    text: str


class Relaxation(Frozen):
    """`fixes`: True if relaxing only this makes the problem feasible, False if not, None if
    untested or undecided within the time limit."""

    kind: RelaxationKind
    target: Id
    text: str
    fixes: bool | None = None


class InfeasibilityReport(Frozen):
    conflicts: tuple[Conflict, ...] = ()
    relaxations: tuple[Relaxation, ...] = ()


_FIXES_RANK = {True: 0, None: 1, False: 2}
_KIND_ORDER: tuple[RelaxationKind, ...] = (
    "switch_to_soft",
    "add_resource",
    "free_resource",
    "unpin",
    "change_param",
)
_KIND_RANK = {kind: i for i, kind in enumerate(_KIND_ORDER)}


def diagnose(
    problem: Problem, time_limit_s: int, cancel: CancelToken | None = None
) -> InfeasibilityReport:
    """Half the time limit finds a conflict set; the rest tests each conflict's relaxation alone.
    A problem not proven infeasible in time gives an empty report."""
    compiled = compile_problem(problem, assumptions=True, relax_core=True)
    model = compiled.model
    literals = {name: model.get_bool_var_from_proto_index(i) for i, name in compiled.hard.items()}
    half = max(1, time_limit_s // 2)
    status, solver = _run(model, list(literals.values()), half, cancel)
    if status != cp_model.INFEASIBLE:
        return InfeasibilityReport()
    found = solver.sufficient_assumptions_for_infeasibility()
    names = sorted(compiled.hard[i] for i in found if i in compiled.hard)
    each = max(1, half // max(1, len(names)))
    rules = {c.id: c for c in problem.constraints}
    pools = {name: key for key, name in requirement_pools(problem).items()}
    conflicts: list[Conflict] = []
    relaxations: list[Relaxation] = []
    for name in names:
        others = [literal for n, literal in literals.items() if n != name]
        fixes = _fixes(_run(model, others, each, cancel)[0])
        conflict, suggested = _relaxations(name, rules, pools, fixes)
        conflicts.append(conflict)
        relaxations += suggested
    relaxations.sort(key=lambda r: (_FIXES_RANK[r.fixes], _KIND_RANK[r.kind], r.target))
    return InfeasibilityReport(conflicts=tuple(conflicts), relaxations=tuple(relaxations))


def _run(
    model: cp_model.CpModel,
    assumptions: Sequence[cp_model.IntVar],
    time_limit_s: int,
    cancel: CancelToken | None,
) -> tuple[cp_model.CpSolverStatus, cp_model.CpSolver]:
    model.clear_assumptions()
    model.add_assumptions(assumptions)
    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = time_limit_s
    solver.parameters.num_workers = 1
    if cancel is None:
        return solver.solve(model), solver
    if cancel.cancelled:
        return cp_model.UNKNOWN, solver
    cancel.attach(solver.stop_search)
    try:
        return solver.solve(model), solver
    finally:
        cancel.attach(None)


def _fixes(status: cp_model.CpSolverStatus) -> bool | None:
    if status in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return True
    if status == cp_model.INFEASIBLE:
        return False
    return None


def _role(role: str, resource_filter: ResourceFilter) -> str:
    text = f"role '{role}'"
    if resource_filter.type_key is not None:
        text += f" of type {resource_filter.type_key}"
    if resource_filter.tags:
        text += f" with tags {', '.join(resource_filter.tags)}"
    if resource_filter.attrs:
        text += " matching " + ", ".join(
            f"{p.attr} {p.op} {p.value}" for p in resource_filter.attrs
        )
    return text


def _relaxations(
    name: str,
    rules: dict[str, ConstraintInstance],
    pools: dict[str, tuple[str, ResourceFilter]],
    fixes: bool | None,
) -> tuple[Conflict, list[Relaxation]]:
    if name in rules:
        instance = rules[name]
        text = describe(instance)
        suggested = [
            Relaxation(
                kind="switch_to_soft",
                target=name,
                text=f"Make '{text}' a preference instead of a hard rule",
                fixes=fixes,
            )
        ]
        relax = get_template(instance.template_key, instance.version).relax
        if relax is not None:
            suggested.append(Relaxation(kind="change_param", target=name, text=relax(instance)))
        return Conflict(id=name, kind="rule", text=text), suggested
    if name.startswith(f"{CORE_UNAVAILABLE}:"):
        resource_id = name.removeprefix(f"{CORE_UNAVAILABLE}:")
        conflict = Conflict(
            id=name, kind="unavailable", text=f"{resource_id} is unavailable when it is needed"
        )
        return conflict, [
            Relaxation(
                kind="free_resource",
                target=name,
                text=f"Make {resource_id} available, or let other resources cover its activities",
                fixes=fixes,
            )
        ]
    if name.startswith(f"{CORE_PIN}:"):
        activity_id = name.removeprefix(f"{CORE_PIN}:")
        return Conflict(id=name, kind="pin", text=f"{activity_id} is pinned"), [
            Relaxation(kind="unpin", target=name, text=f"Unpin {activity_id}", fixes=fixes)
        ]
    role = _role(*pools[name])
    return Conflict(id=name, kind="requirement", text=f"Enough resources for {role}"), [
        Relaxation(kind="add_resource", target=name, text=f"Add a resource for {role}", fixes=fixes)
    ]
