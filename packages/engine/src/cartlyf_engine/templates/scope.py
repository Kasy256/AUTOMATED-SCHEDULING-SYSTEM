from collections import defaultdict

from cartlyf_engine.domain import Activity, Problem, Resource, Scope, predicate_holds


def in_scope(resource: Resource, scope: Scope) -> bool:
    """Every set field must hold: any listed type, all tags, all attrs, any listed id."""
    if scope.resource_type_keys and resource.type_key not in scope.resource_type_keys:
        return False
    if not set(scope.tags) <= set(resource.tags):
        return False
    if scope.resource_ids and resource.id not in scope.resource_ids:
        return False
    return all(predicate_holds(resource.attrs, p) for p in scope.attrs)


def scoped_resources(problem: Problem, scope: Scope) -> list[Resource]:
    return [r for r in problem.resources if in_scope(r, scope)]


def scoped_activities(problem: Problem, scope: Scope) -> list[Activity]:
    if not scope.series_ids:
        return list(problem.activities)
    return [a for a in problem.activities if a.series_id in scope.series_ids]


def series_of(activities: list[Activity]) -> dict[str, list[Activity]]:
    """Activities grouped by series in the given order; ones without a series are left out."""
    grouped: dict[str, list[Activity]] = defaultdict(list)
    for activity in activities:
        if activity.series_id is not None:
            grouped[activity.series_id].append(activity)
    return dict(grouped)
