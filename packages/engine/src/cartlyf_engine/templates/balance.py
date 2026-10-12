from __future__ import annotations

from typing import TYPE_CHECKING, Literal

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance, Problem, Resource, Scope
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Expr, Rule


class Params(Frozen):
    measure: Literal["count", "minutes"]


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def pool(
    problem: Problem, index: ProblemIndex, scope: Scope
) -> tuple[list[Resource], list[Activity]]:
    """In-scope resources that could take at least one in-scope activity, and those activities."""
    activities = scoped_activities(problem, scope)
    resources = [
        r
        for r in scoped_resources(problem, scope)
        if any(r.id in index.candidates(a.id) for a in activities)
    ]
    return resources, activities


def explain(instance: ConstraintInstance) -> str:
    what = "activity counts" if _params(instance).measure == "count" else "minutes worked"
    return f"Even out {what} across resources"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    by_count, enc = _params(instance).measure == "count", rule.enc
    resources, activities = pool(enc.problem, enc.index, instance.scope)
    if len(resources) < 2:
        return
    loads: list[Expr] = []
    top = 0
    for r in resources:
        terms = [
            (1 if by_count else a.duration, enc.uses[a.id, r.id])
            for a in activities
            if (a.id, r.id) in enc.uses
        ]
        loads.append(sum(w * use for w, use in terms))
        top = max(top, sum(w for w, _ in terms))
    hi = rule.model.new_int_var(0, top, "")
    lo = rule.model.new_int_var(0, top, "")
    for load in loads:
        rule.model.add(hi >= load)
        rule.model.add(lo <= load)
    rule.penalize(hi - lo)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    by_count, text = _params(instance).measure == "count", explain(instance)
    resources, activities = pool(ctx.problem, ctx.index, instance.scope)
    if len(resources) < 2:
        return []
    in_scope = {a.id for a in activities}
    loads = {
        r.id: sum(1 if by_count else a.duration for a in ctx.work(r.id) if a.id in in_scope)
        for r in resources
    }
    hi_id, lo_id = max(loads, key=loads.__getitem__), min(loads, key=loads.__getitem__)
    spread = loads[hi_id] - loads[lo_id]
    if not spread:
        return []
    return [
        Finding(
            spread,
            f"{text}: load ranges from {loads[lo_id]} ({lo_id}) to {loads[hi_id]} ({hi_id})",
            (),
            (lo_id, hi_id),
        )
    ]


SPEC = TemplateSpec(
    "balance", 1, Params, soft_only=True, encode=encode, check=check, explain=explain
)
