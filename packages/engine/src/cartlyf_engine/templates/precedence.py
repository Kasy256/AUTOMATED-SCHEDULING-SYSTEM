from __future__ import annotations

from typing import TYPE_CHECKING, Self, cast

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance, Problem, Scope
from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.scope import scoped_activities, series_of
from cartlyf_engine.templates.spec import References, TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Rule


class Pair(Frozen):
    before: Id
    after: Id

    @model_validator(mode="after")
    def _different(self) -> Self:
        if self.before == self.after:
            raise ValueError("before and after must differ")
        return self


class Params(Frozen):
    # Series ids: every activity of `before` ends min_gap minutes before any of `after` starts.
    pairs: tuple[Pair, ...] = Field(min_length=1)
    min_gap: NonNegativeInt = 0


def _references(params: BaseModel) -> References:
    pairs = cast(Params, params).pairs
    return References(series_ids=frozenset(s for p in pairs for s in (p.before, p.after)))


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def _ordered(
    problem: Problem, scope: Scope, pairs: tuple[Pair, ...]
) -> list[tuple[Activity, Activity]]:
    series = series_of(scoped_activities(problem, scope))
    return [
        (before, after)
        for pair in pairs
        for before in series.get(pair.before, [])
        for after in series.get(pair.after, [])
    ]


def explain(instance: ConstraintInstance) -> str:
    gap = _params(instance).min_gap
    return f"Series finish at least {gap} minutes before their successors start"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p, enc = _params(instance), rule.enc
    for before, after in _ordered(enc.problem, instance.scope, p.pairs):
        ready = enc.start[before.id] + before.duration + p.min_gap
        later = enc.start[after.id]
        if rule.hard:
            rule.add(ready <= later)
        else:
            rule.penalize(enc.breach(ready <= later))


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    findings: list[Finding] = []
    for before, after in _ordered(ctx.problem, instance.scope, p.pairs):
        if before.id not in ctx.placed or after.id not in ctx.placed:
            continue
        end = ctx.placed[before.id].start + before.duration
        start = ctx.placed[after.id].start
        if end + p.min_gap > start:
            findings.append(
                Finding(
                    1,
                    f"{text}: {before.id} ends at {end}, {after.id} starts at {start}",
                    (before.id, after.id),
                )
            )
    return findings


SPEC = TemplateSpec(
    "precedence", 1, Params, references=_references, encode=encode, check=check, explain=explain
)
