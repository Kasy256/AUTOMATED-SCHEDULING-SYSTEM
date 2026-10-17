from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from pydantic import Field, model_validator

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance, Problem, Scope
from cartlyf_engine.domain.base import Frozen, Key
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Expr, Rule


class Params(Frozen):
    headcount_from: Literal["group_sizes", "activity_attr"] = Field(
        default="group_sizes", title="Headcount from"
    )
    headcount_attr: Key | None = Field(
        default=None,
        title="Headcount attribute",
        description="Activity attribute holding the headcount",
    )

    @model_validator(mode="after")
    def _attr_when_needed(self) -> Self:
        if (self.headcount_from == "activity_attr") != (self.headcount_attr is not None):
            raise ValueError(
                "headcount_attr is required exactly when headcount_from is activity_attr"
            )
        return self


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def _attr_headcount(activity: Activity, attr: str | None) -> int | None:
    value = activity.attrs.get(attr) if attr is not None else None
    # Activity attrs are customer data; a negative headcount is treated as missing.
    if isinstance(value, int) and not isinstance(value, bool) and value >= 0:
        return value
    return None


def _spaces(problem: Problem, scope: Scope) -> dict[str, int]:
    return {
        r.id: r.capacity
        for r in scoped_resources(problem, scope)
        if r.kind == "space" and r.capacity is not None
    }


def explain(instance: ConstraintInstance) -> str:
    if instance.hard:
        return "A space must seat the activity's headcount"
    return "A space's capacity should match the activity's headcount"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    params, enc = _params(instance), rule.enc
    spaces = _spaces(enc.problem, instance.scope)
    for activity in scoped_activities(enc.problem, instance.scope):
        candidates = enc.index.candidates(activity.id)
        headcount: Expr
        if params.headcount_from == "activity_attr":
            fixed = _attr_headcount(activity, params.headcount_attr)
            if fixed is None:
                continue
            headcount, most = fixed, fixed
        else:
            sizes: dict[str, int] = {}
            for resource_id in sorted(candidates):
                resource = enc.index.resources[resource_id]
                if resource.kind == "group" and resource.size is not None:
                    sizes[resource_id] = resource.size
            headcount = sum(size * enc.uses[activity.id, g] for g, size in sizes.items())
            most = sum(sizes.values())
        for space_id in sorted(candidates & spaces.keys()):
            capacity, use = spaces[space_id], enc.uses[activity.id, space_id]
            if rule.hard:
                if most > capacity:
                    rule.add(headcount <= capacity, use)
                continue
            seats = rule.model.new_int_var(0, max(capacity, most), "")
            rule.enc.when(seats >= capacity - headcount, use)
            rule.enc.when(seats >= headcount - capacity, use)
            rule.penalize(seats)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    params, text = _params(instance), explain(instance)
    spaces = _spaces(ctx.problem, instance.scope)
    findings: list[Finding] = []
    for activity in scoped_activities(ctx.problem, instance.scope):
        if activity.id not in ctx.placed:
            continue
        holders = ctx.holders(activity.id)
        if params.headcount_from == "activity_attr":
            attr_headcount = _attr_headcount(activity, params.headcount_attr)
            if attr_headcount is None:
                continue
            headcount = attr_headcount
        else:
            headcount = 0
            for resource_id in holders:
                resource = ctx.index.resources[resource_id]
                if resource.kind == "group" and resource.size is not None:
                    headcount += resource.size
        for space_id in sorted(holders & spaces.keys()):
            capacity = spaces[space_id]
            amount = max(0, headcount - capacity) if instance.hard else abs(capacity - headcount)
            if amount:
                findings.append(
                    Finding(
                        amount,
                        f"{text}: {space_id} seats {capacity}, {activity.id} has {headcount}",
                        (activity.id,),
                        (space_id,),
                    )
                )
    return findings


SPEC = TemplateSpec(
    "capacity_fit",
    1,
    Params,
    encode=encode,
    check=check,
    explain=explain,
    title="Capacity fit",
    description="A space's capacity covers the headcount of the activity it hosts.",
)
