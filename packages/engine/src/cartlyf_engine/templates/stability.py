from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import Field, NonNegativeInt

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, Assignment, ConstraintInstance, Problem
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.scope import in_scope, scoped_activities
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Expr, Rule


class Params(Frozen):
    per_change: NonNegativeInt = Field(title="Penalty per moved activity")
    per_resource_change: NonNegativeInt = Field(title="Penalty per replaced resource")


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def explain(instance: ConstraintInstance) -> str:
    p = _params(instance)
    return (
        f"Stay close to the published plan ({p.per_change} per moved activity, "
        f"{p.per_resource_change} per replaced resource)"
    )


def _kept(
    problem: Problem, instance: ConstraintInstance
) -> list[tuple[Activity, Assignment, tuple[str, ...]]]:
    """In-scope activities with a baseline placement, and their in-scope baseline resources.
    Activities and resources that no longer exist are ignored."""
    if problem.baseline is None:
        return []
    baseline = {b.activity_id: b for b in problem.baseline}
    resources = {r.id: r for r in problem.resources}
    kept: list[tuple[Activity, Assignment, tuple[str, ...]]] = []
    for activity in scoped_activities(problem, instance.scope):
        before = baseline.get(activity.id)
        if before is None:
            continue
        held = {
            r
            for ids in before.resources.values()
            for r in ids
            if r in resources and in_scope(resources[r], instance.scope)
        }
        kept.append((activity, before, tuple(sorted(held))))
    return kept


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p, enc = _params(instance), rule.enc
    for activity, before, held in _kept(enc.problem, instance):
        literals = enc.starts[activity.id]
        moved: Expr = 1 - literals[before.start] if before.start in literals else 1
        dropped: list[Expr] = [
            1 - enc.uses[activity.id, r] if (activity.id, r) in enc.uses else 1 for r in held
        ]
        rule.penalize(p.per_change * moved + p.per_resource_change * sum(dropped))


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    findings: list[Finding] = []
    for activity, before, held in _kept(ctx.problem, instance):
        after = ctx.placed.get(activity.id)
        if after is None:
            continue
        amount, changes = 0, list[str]()
        if after.start != before.start:
            amount += p.per_change
            changes.append(f"moved from minute {before.start} to {after.start}")
        dropped = tuple(r for r in held if r not in ctx.holders(activity.id))
        if dropped:
            amount += p.per_resource_change * len(dropped)
            changes.append(f"no longer has {', '.join(dropped)}")
        if changes:
            message = f"{text}: {activity.id} {' and '.join(changes)}"
            findings.append(Finding(amount, message, (activity.id,), dropped))
    return findings


SPEC = TemplateSpec(
    "stability",
    1,
    Params,
    soft_only=True,
    encode=encode,
    check=check,
    explain=explain,
    title="Stability",
    description="Keeps repairs close to the published schedule.",
)
