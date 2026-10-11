from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, cast

from pydantic import AfterValidator, BaseModel, Field

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance, Problem, Scope
from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.scope import scoped_activities, series_of
from cartlyf_engine.templates.spec import References, TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Rule


def _distinct_pairable(group: tuple[str, ...]) -> tuple[str, ...]:
    if len(group) < 2 or len(set(group)) != len(group):
        raise ValueError("a link group needs at least two distinct series ids")
    return group


# Series ids, not activity ids: the i-th activity of each linked series starts together.
LinkGroup = Annotated[tuple[Id, ...], AfterValidator(_distinct_pairable)]


class Params(Frozen):
    link_groups: tuple[LinkGroup, ...] = Field(min_length=1)


def _references(params: BaseModel) -> References:
    groups = cast(Params, params).link_groups
    return References(series_ids=frozenset(s for group in groups for s in group))


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def linked_pairs(
    problem: Problem, scope: Scope, groups: tuple[tuple[str, ...], ...]
) -> list[tuple[Activity, Activity]]:
    """The i-th activity of each linked series paired with the i-th of the group's first series."""
    series = series_of(scoped_activities(problem, scope))
    pairs: list[tuple[Activity, Activity]] = []
    for group in groups:
        lists = [series.get(s, []) for s in group]
        for i in range(min(len(items) for items in lists)):
            pairs += [(lists[0][i], other[i]) for other in lists[1:]]
    return pairs


def explain(instance: ConstraintInstance) -> str:
    return "Linked series start at the same time"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    enc = rule.enc
    for first, other in linked_pairs(enc.problem, instance.scope, _params(instance).link_groups):
        a, b = enc.start[first.id], enc.start[other.id]
        if rule.hard:
            rule.add(a == b)
        else:
            rule.penalize(enc.holds(a != b, a == b))


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    text = explain(instance)
    findings: list[Finding] = []
    for first, other in linked_pairs(ctx.problem, instance.scope, _params(instance).link_groups):
        if first.id not in ctx.placed or other.id not in ctx.placed:
            continue
        a, b = ctx.placed[first.id].start, ctx.placed[other.id].start
        if a != b:
            findings.append(
                Finding(
                    1, f"{text}: {first.id} starts at {a}, {other.id} at {b}", (first.id, other.id)
                )
            )
    return findings


SPEC = TemplateSpec(
    "same_time", 1, Params, references=_references, encode=encode, check=check, explain=explain
)
