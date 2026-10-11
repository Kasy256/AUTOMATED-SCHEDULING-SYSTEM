from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self, cast

from pydantic import BaseModel, model_validator

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import ConstraintInstance, Resource, Scope
from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources, series_of
from cartlyf_engine.templates.spec import References, TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Rule


class Pair(Frozen):
    resource_id: Id
    series_id: Id
    mode: Literal["prefer", "avoid"]


class Params(Frozen):
    source: Literal["calendar", "explicit"]
    pairs: tuple[Pair, ...] = ()

    @model_validator(mode="after")
    def _pairs_match_source(self) -> Self:
        if (self.source == "explicit") != bool(self.pairs):
            raise ValueError("pairs are required for explicit preferences and only for them")
        return self


def _references(params: BaseModel) -> References:
    pairs = cast(Params, params).pairs
    return References(
        series_ids=frozenset(p.series_id for p in pairs),
        resource_ids=frozenset(p.resource_id for p in pairs),
    )


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def explain(instance: ConstraintInstance) -> str:
    if _params(instance).source == "calendar":
        return "Respect preferred and avoided times"
    return "Respect preferred and avoided assignments"


def _cost(resource: Resource, start: int, duration: int) -> int:
    end = start + duration
    avoided = any(start < w.end and w.start < end for w in resource.avoided)
    outside = bool(resource.preferred) and not any(
        w.start <= start and end <= w.end for w in resource.preferred
    )
    return int(avoided) + int(outside)


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p = _params(instance)
    if p.source == "calendar":
        _encode_calendar(rule, instance.scope)
    else:
        _encode_explicit(rule, instance.scope, p.pairs)


def _encode_calendar(rule: Rule, scope: Scope) -> None:
    enc = rule.enc
    activities = scoped_activities(enc.problem, scope)
    for resource in scoped_resources(enc.problem, scope):
        if not (resource.preferred or resource.avoided):
            continue
        for a in activities:
            use = enc.uses.get((a.id, resource.id))
            if use is None:
                continue
            costs = {s: _cost(resource, s, a.duration) for s in a.candidate_starts}
            if any(costs.values()):
                cost = sum(c * enc.starts[a.id][s] for s, c in costs.items() if c)
                rule.penalize(enc.gate(cost, use, max(costs.values())))


def _encode_explicit(rule: Rule, scope: Scope, pairs: tuple[Pair, ...]) -> None:
    enc = rule.enc
    resources = {r.id for r in scoped_resources(enc.problem, scope)}
    series = series_of(scoped_activities(enc.problem, scope))
    for pair in pairs:
        if pair.resource_id not in resources:
            continue
        for a in series.get(pair.series_id, []):
            use = enc.uses.get((a.id, pair.resource_id))
            if pair.mode == "avoid":
                if use is not None:
                    rule.penalize(use)
            else:
                rule.penalize(1 - use if use is not None else 1)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    findings: list[Finding] = []
    if p.source == "calendar":
        in_scope = {a.id for a in scoped_activities(ctx.problem, instance.scope)}
        for resource in scoped_resources(ctx.problem, instance.scope):
            for a in ctx.work(resource.id):
                if a.id not in in_scope:
                    continue
                start = ctx.placed[a.id].start
                end = start + a.duration
                if any(w.start < end and start < w.end for w in resource.avoided):
                    findings.append(
                        Finding(
                            1,
                            f"{text}: {a.id} for {resource.id} overlaps an avoided time",
                            (a.id,),
                            (resource.id,),
                        )
                    )
                if resource.preferred and not any(
                    w.start <= start and end <= w.end for w in resource.preferred
                ):
                    findings.append(
                        Finding(
                            1,
                            f"{text}: {a.id} for {resource.id} is outside preferred times",
                            (a.id,),
                            (resource.id,),
                        )
                    )
        return findings
    resources = {r.id for r in scoped_resources(ctx.problem, instance.scope)}
    series = series_of(scoped_activities(ctx.problem, instance.scope))
    for pair in p.pairs:
        if pair.resource_id not in resources:
            continue
        for a in series.get(pair.series_id, []):
            if a.id not in ctx.placed:
                continue
            on = pair.resource_id in ctx.holders(a.id)
            if pair.mode == "avoid" and on:
                findings.append(
                    Finding(
                        1,
                        f"{text}: {pair.resource_id} is on {a.id}, which it should avoid",
                        (a.id,),
                        (pair.resource_id,),
                    )
                )
            if pair.mode == "prefer" and not on:
                findings.append(
                    Finding(
                        1,
                        f"{text}: {pair.resource_id} is not on {a.id}, which it prefers",
                        (a.id,),
                        (pair.resource_id,),
                    )
                )
    return findings


SPEC = TemplateSpec(
    "preference",
    1,
    Params,
    soft_only=True,
    references=_references,
    encode=encode,
    check=check,
    explain=explain,
)
