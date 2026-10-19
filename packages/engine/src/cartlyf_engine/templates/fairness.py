from __future__ import annotations

from collections.abc import Iterable
from typing import TYPE_CHECKING, cast

from pydantic import BaseModel, Field, NonNegativeInt

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import (
    Activity,
    Assignment,
    ConstraintInstance,
    Problem,
    Resource,
    activity_matches,
)
from cartlyf_engine.domain.base import Frozen, Key
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.scope import in_scope, scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import References, TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Expr, Rule


class Params(Frozen):
    counter: Key = Field(title="Ledger counter")
    activity_filter: ActivityFilter = Field(title="Counts activities")
    lookback_days: NonNegativeInt = Field(title="Look back (days)")


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def _references(params: BaseModel) -> References:
    return References(series_ids=frozenset(cast(Params, params).activity_filter.series_ids))


def _counted_activities(problem: Problem, instance: ConstraintInstance) -> list[Activity]:
    activity_filter = _params(instance).activity_filter
    return [
        a
        for a in scoped_activities(problem, instance.scope)
        if activity_matches(a, activity_filter)
    ]


def _free_at_some_start(resource: Resource, activity: Activity) -> bool:
    return any(
        all(w.end <= s or s + activity.duration <= w.start for w in resource.unavailable)
        for s in activity.candidate_starts
    )


def pool(
    problem: Problem, index: ProblemIndex, instance: ConstraintInstance
) -> tuple[list[Resource], list[Activity]]:
    """In-scope resources that could take a counted activity at a start they are free, and the
    counted activities."""
    activities = _counted_activities(problem, instance)
    resources = [
        r
        for r in scoped_resources(problem, instance.scope)
        if any(r.id in index.candidates(a.id) and _free_at_some_start(r, a) for a in activities)
    ]
    return resources, activities


def _history(problem: Problem, instance: ConstraintInstance) -> dict[str, int]:
    return (problem.history or {}).get(instance.id, {})


def counted(
    problem: Problem, instance: ConstraintInstance, assignments: Iterable[Assignment]
) -> dict[str, list[int]]:
    """In-scope resource id -> starts of its assignments to counted activities; others omitted."""
    activity_ids = {a.id for a in _counted_activities(problem, instance)}
    resources = {r.id for r in problem.resources if in_scope(r, instance.scope)}
    starts: dict[str, list[int]] = {}
    for assignment in assignments:
        if assignment.activity_id not in activity_ids:
            continue
        holders = {r for ids in assignment.resources.values() for r in ids if r in resources}
        for resource_id in holders:
            starts.setdefault(resource_id, []).append(assignment.start)
    return {r: sorted(s) for r, s in starts.items()}


def explain(instance: ConstraintInstance) -> str:
    p = _params(instance)
    return f"Share {p.counter} fairly, counting the last {p.lookback_days} days"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    enc = rule.enc
    resources, activities = pool(enc.problem, enc.index, instance)
    if len(resources) < 2:
        return
    history = _history(enc.problem, instance)
    loads: list[Expr] = []
    for r in resources:
        uses = [enc.uses[a.id, r.id] for a in activities if (a.id, r.id) in enc.uses]
        loads.append(history.get(r.id, 0) + sum(uses))
    top = max((history.get(r.id, 0) for r in resources), default=0) + len(activities)
    hi = rule.model.new_int_var(0, top, "")
    lo = rule.model.new_int_var(0, top, "")
    for load in loads:
        rule.model.add(hi >= load)
        rule.model.add(lo <= load)
    rule.penalize(hi - lo)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    resources, _ = pool(ctx.problem, ctx.index, instance)
    if len(resources) < 2:
        return []
    history = _history(ctx.problem, instance)
    starts = counted(ctx.problem, instance, ctx.placed.values())
    totals = {r.id: history.get(r.id, 0) + len(starts.get(r.id, [])) for r in resources}
    hi_id, lo_id = max(totals, key=totals.__getitem__), min(totals, key=totals.__getitem__)
    spread = totals[hi_id] - totals[lo_id]
    if not spread:
        return []
    return [
        Finding(
            spread,
            f"{explain(instance)}: totals range from {totals[lo_id]} ({lo_id}) "
            f"to {totals[hi_id]} ({hi_id})",
            (),
            (lo_id, hi_id),
        )
    ]


SPEC = TemplateSpec(
    "fairness",
    1,
    Params,
    soft_only=True,
    whole_scope=True,
    references=_references,
    encode=encode,
    check=check,
    explain=explain,
    title="Fairness over time",
    description="Shares unpopular work fairly, counting past schedules.",
)
