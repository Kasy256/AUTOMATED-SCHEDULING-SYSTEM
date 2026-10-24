"""Pre-solve feasibility check: cheap necessary conditions, so obvious impossibilities are
reported before a solve. Passing it does not mean the problem is feasible.

- unfillable_requirement: a hard requirement needs more resources than match its filter.
- fixed_resource_mismatch: a fixed resource does not match its requirement's filter.
- insufficient_capacity: hard requirements sharing one filter need more resource-minutes than
  the matching resources have available (x concurrency).
- overloaded_resource: a resource is fixed on more activity minutes than it has available.
"""

from collections import defaultdict
from typing import Literal

from cartlyf_engine.domain import (
    Activity,
    Frozen,
    Id,
    Problem,
    Resource,
    ResourceFilter,
    resource_matches,
)

IssueCode = Literal[
    "unfillable_requirement",
    "fixed_resource_mismatch",
    "insufficient_capacity",
    "overloaded_resource",
]


class Issue(Frozen):
    code: IssueCode
    message: str
    activity_ids: tuple[Id, ...] = ()
    resource_ids: tuple[Id, ...] = ()


def available_minutes(resource: Resource, horizon_minutes: int) -> int:
    blocked, cursor = 0, 0
    for window in sorted(resource.unavailable, key=lambda w: w.start):
        start, end = max(window.start, cursor), min(window.end, horizon_minutes)
        if end > start:
            blocked += end - start
        cursor = max(cursor, window.end)
    return horizon_minutes - blocked


def precheck(problem: Problem) -> list[Issue]:
    supply = {
        r.id: available_minutes(r, problem.horizon_minutes) * r.concurrency
        for r in problem.resources
    }
    by_id = {r.id: r for r in problem.resources}
    issues: list[Issue] = []
    pooled: dict[ResourceFilter, list[tuple[Activity, int]]] = defaultdict(list)
    fixed_load: dict[str, list[Activity]] = defaultdict(list)

    for activity in problem.activities:
        for req in activity.requirements:
            if not req.hard:
                continue
            matching = [r.id for r in problem.resources if resource_matches(r, req.filter)]
            if len(matching) < req.count_min:
                issues.append(
                    Issue(
                        code="unfillable_requirement",
                        message=f"Requirement '{req.role}' needs {req.count_min} resources "
                        f"but {len(matching)} match its filter",
                        activity_ids=(activity.id,),
                    )
                )
            for fixed in req.fixed_resource_ids:
                fixed_load[fixed].append(activity)
                if not resource_matches(by_id[fixed], req.filter):
                    issues.append(
                        Issue(
                            code="fixed_resource_mismatch",
                            message=f"Fixed resource {fixed} does not match requirement "
                            f"'{req.role}'",
                            activity_ids=(activity.id,),
                            resource_ids=(fixed,),
                        )
                    )
            free = req.count_min - len(req.fixed_resource_ids)
            if free > 0:
                pooled[req.filter].append((activity, free))

    for resource_filter, needs in pooled.items():
        demand = sum(a.duration * n for a, n in needs)
        matching = sorted(r.id for r in problem.resources if resource_matches(r, resource_filter))
        available = sum(supply[i] for i in matching)
        if matching and demand > available:
            issues.append(
                Issue(
                    code="insufficient_capacity",
                    message=f"Activities need {demand} resource-minutes but the matching "
                    f"resources have {available} available",
                    activity_ids=tuple(sorted({a.id for a, _ in needs})),
                    resource_ids=tuple(matching),
                )
            )

    for resource_id, activities in sorted(fixed_load.items()):
        demand = sum(a.duration for a in activities)
        if demand > supply[resource_id]:
            issues.append(
                Issue(
                    code="overloaded_resource",
                    message=f"Resource {resource_id} is fixed on {demand} minutes of activities "
                    f"but has {supply[resource_id]} available",
                    activity_ids=tuple(sorted({a.id for a in activities})),
                    resource_ids=(resource_id,),
                )
            )
    return sorted(issues, key=lambda i: (i.code, i.activity_ids, i.resource_ids))
