"""Independent checker: scores assignments against a Problem in plain Python.

It never imports OR-Tools (import-linter), so it can verify every solver result and every
planner move."""

from collections import defaultdict
from collections.abc import Sequence

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import (
    CORE_OVERLAP,
    CORE_PIN,
    CORE_PLACEMENT,
    CORE_REQUIREMENT,
    CORE_UNAVAILABLE,
    REQUIREMENTS_TERM,
    Assignment,
    PenaltyTerm,
    Problem,
    Score,
    Violation,
    resource_matches,
)
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.registry import UnsupportedTemplate, get_template

_DETAILS_SHOWN = 5


def check(problem: Problem, assignments: Sequence[Assignment]) -> Score:
    index = ProblemIndex(problem)
    violations: list[Violation] = []
    placed = _placement(problem, index, assignments, violations)
    shortfalls = _requirements(index, placed, violations)
    _overlaps(problem, index, placed, violations)
    _pins(problem, placed, violations)

    ctx = CheckContext(problem, index, placed)
    terms: list[PenaltyTerm] = []
    for instance in problem.constraints:
        spec = get_template(instance.template_key, instance.version)
        if spec.check is None:
            raise UnsupportedTemplate(instance.template_key)
        findings = spec.check(ctx, instance)
        if instance.hard:
            violations += [
                Violation(
                    constraint_id=instance.id,
                    message=f.message,
                    activity_ids=f.activity_ids,
                    resource_ids=f.resource_ids,
                )
                for f in findings
                if f.amount > 0
            ]
        else:
            terms.append(_term(instance.id, instance.weight, findings))
    if any(not r.hard and r.count_min > 0 for a in problem.activities for r in a.requirements):
        terms.append(_term(REQUIREMENTS_TERM, 1, shortfalls))
    return Score(
        hard_violations=len(violations),
        soft_total=sum(t.penalty for t in terms),
        terms=tuple(terms),
        violations=tuple(violations),
    )


def _term(constraint_id: str, weight: int, findings: list[Finding]) -> PenaltyTerm:
    breaches = [f for f in findings if f.amount > 0]
    details = "; ".join(f.message for f in breaches[:_DETAILS_SHOWN])
    if len(breaches) > _DETAILS_SHOWN:
        details += f" (+{len(breaches) - _DETAILS_SHOWN} more)"
    return PenaltyTerm(
        constraint_id=constraint_id,
        penalty=weight * sum(f.amount for f in breaches),
        details=details,
    )


def _core(rule: str, message: str, activity_id: str, *resource_ids: str) -> Violation:
    return Violation(
        constraint_id=rule,
        message=message,
        activity_ids=(activity_id,),
        resource_ids=resource_ids,
    )


def _placement(
    problem: Problem,
    index: ProblemIndex,
    assignments: Sequence[Assignment],
    violations: list[Violation],
) -> dict[str, Assignment]:
    placed: dict[str, Assignment] = {}
    seen: set[str] = set()
    for a in assignments:
        activity = index.activities.get(a.activity_id)
        if activity is None:
            violations.append(
                _core(CORE_PLACEMENT, f"Unknown activity {a.activity_id}", a.activity_id)
            )
        elif a.activity_id in seen:
            violations.append(
                _core(CORE_PLACEMENT, f"{a.activity_id} is placed more than once", a.activity_id)
            )
        elif a.start not in activity.candidate_starts:
            violations.append(
                _core(
                    CORE_PLACEMENT,
                    f"{a.activity_id} starts at {a.start}, which is not a candidate start",
                    a.activity_id,
                )
            )
        else:
            placed[a.activity_id] = a
        seen.add(a.activity_id)
    for activity in problem.activities:
        if activity.id not in seen:
            violations.append(_core(CORE_PLACEMENT, f"{activity.id} is not placed", activity.id))
    return placed


def _requirements(
    index: ProblemIndex, placed: dict[str, Assignment], violations: list[Violation]
) -> list[Finding]:
    shortfalls: list[Finding] = []
    for activity_id, assignment in placed.items():
        activity = index.activities[activity_id]
        roles = {req.role: req for req in activity.requirements}
        seen: set[str] = set()
        for role, ids in assignment.resources.items():
            if role not in roles:
                violations.append(
                    _core(CORE_REQUIREMENT, f"{activity_id} has no role '{role}'", activity_id)
                )
                continue
            for r in ids:
                if r not in index.resources:
                    violations.append(
                        _core(
                            CORE_REQUIREMENT,
                            f"{activity_id} names unknown resource {r}",
                            activity_id,
                        )
                    )
                elif not resource_matches(index.resources[r], roles[role].filter):
                    violations.append(
                        _core(
                            CORE_REQUIREMENT,
                            f"{r} does not match role '{role}' of {activity_id}",
                            activity_id,
                            r,
                        )
                    )
                if r in seen:
                    violations.append(
                        _core(
                            CORE_REQUIREMENT,
                            f"{r} fills more than one place in {activity_id}",
                            activity_id,
                            r,
                        )
                    )
                seen.add(r)
        for req in activity.requirements:
            ids = assignment.resources.get(req.role, ())
            where = f"Role '{req.role}' of {activity_id}"
            if len(ids) > req.count_max:
                violations.append(
                    _core(
                        CORE_REQUIREMENT,
                        f"{where} has {len(ids)} resources, at most {req.count_max} allowed",
                        activity_id,
                    )
                )
            if len(ids) < req.count_min:
                if req.hard:
                    violations.append(
                        _core(
                            CORE_REQUIREMENT,
                            f"{where} has {len(ids)} resources, needs {req.count_min}",
                            activity_id,
                        )
                    )
                else:
                    missing = req.count_min - len(ids)
                    shortfalls.append(
                        Finding(
                            req.weight * missing, f"{where} is short by {missing}", (activity_id,)
                        )
                    )
            for r in req.fixed_resource_ids:
                if r not in ids:
                    violations.append(
                        _core(
                            CORE_REQUIREMENT,
                            f"{r} is fixed on role '{req.role}' of {activity_id} but not assigned",
                            activity_id,
                            r,
                        )
                    )
    return shortfalls


def _overlaps(
    problem: Problem,
    index: ProblemIndex,
    placed: dict[str, Assignment],
    violations: list[Violation],
) -> None:
    work: dict[str, list[tuple[int, int, str]]] = defaultdict(list)
    for activity_id, assignment in placed.items():
        end = assignment.start + index.activities[activity_id].duration
        holders = {r for ids in assignment.resources.values() for r in ids if r in index.resources}
        for r in holders:
            work[r].append((assignment.start, end, activity_id))
    for resource in problem.resources:
        items = sorted(work[resource.id])
        for start, end, activity_id in items:
            for w in resource.unavailable:
                if start < w.end and w.start < end:
                    violations.append(
                        _core(
                            CORE_UNAVAILABLE,
                            f"{resource.id} is unavailable during {activity_id} "
                            f"(minutes {w.start}-{w.end})",
                            activity_id,
                            resource.id,
                        )
                    )
        # Load peaks at some activity's start, so checking those instants is enough.
        for instant in sorted({start for start, _, _ in items}):
            running = [a for s, e, a in items if s <= instant < e]
            if len(running) > resource.concurrency:
                violations.append(
                    Violation(
                        constraint_id=CORE_OVERLAP,
                        message=f"{resource.id} is in {len(running)} activities at minute "
                        f"{instant}, limit {resource.concurrency}",
                        activity_ids=tuple(sorted(running)),
                        resource_ids=(resource.id,),
                    )
                )


def _pins(problem: Problem, placed: dict[str, Assignment], violations: list[Violation]) -> None:
    for activity in problem.activities:
        pin, assignment = activity.pinned, placed.get(activity.id)
        if pin is None or assignment is None:
            continue
        if pin.start is not None and assignment.start != pin.start:
            violations.append(
                _core(
                    CORE_PIN,
                    f"{activity.id} is pinned to start {pin.start} "
                    f"but starts at {assignment.start}",
                    activity.id,
                )
            )
        for role, ids in pin.resources.items():
            missing = sorted(set(ids) - set(assignment.resources.get(role, ())))
            if missing:
                violations.append(
                    _core(
                        CORE_PIN,
                        f"{activity.id} is pinned to {', '.join(missing)} in role '{role}'",
                        activity.id,
                        *missing,
                    )
                )
