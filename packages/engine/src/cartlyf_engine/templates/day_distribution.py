from __future__ import annotations

from collections import Counter
from typing import TYPE_CHECKING

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar

    from cartlyf_engine.encoding import Expr, Rule


class Params(Frozen):
    pass


def usable_days(index: ProblemIndex, activities: list[Activity], resource_id: str) -> list[int]:
    """Days on which one of the resource's possible activities could start."""
    days: set[int] = set()
    for a in activities:
        if resource_id in index.candidates(a.id):
            for start in a.candidate_starts:
                day = index.attribute(start, "day", None)
                if day is not None:
                    days.add(day)
    return sorted(days)


def explain(instance: ConstraintInstance) -> str:
    return "Spread each resource's activities evenly across days"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    enc = rule.enc
    activities = scoped_activities(enc.problem, instance.scope)
    for resource in scoped_resources(enc.problem, instance.scope):
        days = usable_days(enc.index, activities, resource.id)
        if len(days) < 2:
            continue
        counts: list[Expr] = []
        for day in days:
            lits: list[IntVar] = []
            for a in activities:
                starts = [
                    s for s in a.candidate_starts if enc.index.attribute(s, "day", None) == day
                ]
                lit = enc.assigned_at(a.id, resource.id, starts, "exact")
                if not isinstance(lit, int):
                    lits.append(lit)
            counts.append(sum(lits))
        top = sum(1 for a in activities if (a.id, resource.id) in enc.uses)
        hi = rule.model.new_int_var(0, top, "")
        rule.model.add_max_equality(hi, counts)
        lo = rule.model.new_int_var(0, top, "")
        rule.model.add_min_equality(lo, counts)
        rule.penalize(hi - lo)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    text = explain(instance)
    activities = scoped_activities(ctx.problem, instance.scope)
    in_scope = {a.id for a in activities}
    findings: list[Finding] = []
    for resource in scoped_resources(ctx.problem, instance.scope):
        days = usable_days(ctx.index, activities, resource.id)
        if len(days) < 2:
            continue
        per_day = Counter(
            ctx.index.attribute(ctx.placed[a.id].start, "day", None)
            for a in ctx.work(resource.id)
            if a.id in in_scope
        )
        counts = [per_day.get(d, 0) for d in days]
        spread = max(counts) - min(counts)
        if spread:
            findings.append(
                Finding(
                    spread,
                    f"{text}: {resource.id} has between {min(counts)} and {max(counts)} "
                    "activities per day",
                    (),
                    (resource.id,),
                )
            )
    return findings


SPEC = TemplateSpec(
    "day_distribution", 1, Params, soft_only=True, encode=encode, check=check, explain=explain
)
