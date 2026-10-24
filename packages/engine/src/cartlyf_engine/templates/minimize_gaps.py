from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING

from pydantic import Field, JsonValue, PositiveInt

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar

    from cartlyf_engine.encoding import Encoding, Rule


MINUTES: dict[str, JsonValue] = {"x-unit": "minutes"}


class Params(Frozen):
    per_minutes: PositiveInt = Field(
        title="Penalty every",
        description="One penalty unit per this many idle minutes",
        json_schema_extra=MINUTES,
    )


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def explain(instance: ConstraintInstance) -> str:
    per = _params(instance).per_minutes
    return f"Keep idle time between a resource's activities short (per {per} minutes)"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    per, enc = _params(instance).per_minutes, rule.enc
    activities = scoped_activities(enc.problem, instance.scope)
    by_day: dict[str, dict[int, list[int]]] = {}
    for a in activities:
        days: dict[int, list[int]] = defaultdict(list)
        for start in a.candidate_starts:
            day = enc.index.attribute(start, "day", None)
            if day is not None:
                days[day].append(start)
        by_day[a.id] = days
    for resource in scoped_resources(enc.problem, instance.scope):
        for day in range(len(enc.problem.day_windows)):
            items: list[tuple[Activity, IntVar]] = []
            for a in activities:
                lit = enc.assigned_at(a.id, resource.id, by_day[a.id].get(day, []), "exact")
                if not isinstance(lit, int):
                    items.append((a, lit))
            if len(items) > 1:
                rule.penalize(_idle_blocks(enc, items, per))


def _idle_blocks(enc: Encoding, items: list[tuple[Activity, IntVar]], per: int) -> IntVar:
    """per * blocks >= last end - first start - busy - per + 1 over the present items, so blocks
    is at least floor(idle / per); minimisation makes it exactly that."""
    m, horizon = enc.model, enc.problem.horizon_minutes
    lo = m.new_int_var(0, horizon, "")
    hi = m.new_int_var(0, horizon, "")
    for a, lit in items:
        enc.when(lo <= enc.start[a.id], lit)
        enc.when(hi >= enc.start[a.id] + a.duration, lit)
    blocks = m.new_int_var(0, horizon // per, "")
    m.add(per * blocks >= hi - lo - sum(a.duration * lit for a, lit in items) - per + 1)
    return blocks


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    per, text = _params(instance).per_minutes, explain(instance)
    in_scope = {a.id for a in scoped_activities(ctx.problem, instance.scope)}
    findings: list[Finding] = []
    for resource in scoped_resources(ctx.problem, instance.scope):
        on_day: dict[int, list[Activity]] = defaultdict(list)
        for a in ctx.work(resource.id):
            if a.id in in_scope:
                day = ctx.index.attribute(ctx.placed[a.id].start, "day", None)
                if day is not None:
                    on_day[day].append(a)
        for day, acts in sorted(on_day.items()):
            starts = [ctx.placed[a.id].start for a in acts]
            span = max(s + a.duration for s, a in zip(starts, acts, strict=True)) - min(starts)
            idle = max(0, span - sum(a.duration for a in acts))
            if idle // per:
                findings.append(
                    Finding(
                        idle // per,
                        f"{text}: {resource.id} is idle {idle} minutes on day {day + 1}",
                        tuple(a.id for a in acts),
                        (resource.id,),
                    )
                )
    return findings


SPEC = TemplateSpec(
    "minimize_gaps",
    1,
    Params,
    soft_only=True,
    encode=encode,
    check=check,
    explain=explain,
    title="Compact days",
    description="Penalises idle time between a resource's activities on one day.",
)
