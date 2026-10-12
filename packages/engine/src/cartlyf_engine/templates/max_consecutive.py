from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Literal, cast

from pydantic import BaseModel, PositiveInt

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance, activity_matches
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import References, TemplateSpec
from cartlyf_engine.templates.text import count

if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar

    from cartlyf_engine.encoding import Rule


class Params(Frozen):
    # "activities" (runs in a resource's sequence) is roadmap: no v1 template needs it.
    unit: Literal["days"]
    max: PositiveInt
    activity_filter: ActivityFilter | None = None


def _references(params: BaseModel) -> References:
    activity_filter = cast(Params, params).activity_filter
    return References(series_ids=frozenset(activity_filter.series_ids if activity_filter else ()))


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def _counted(p: Params, activities: list[Activity]) -> list[Activity]:
    if p.activity_filter is None:
        return activities
    return [a for a in activities if activity_matches(a, p.activity_filter)]


def explain(instance: ConstraintInstance) -> str:
    p = _params(instance)
    what = " on matching activities" if p.activity_filter else ""
    return f"At most {count(p.max, 'consecutive day', 'consecutive days')} worked{what}"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p, enc = _params(instance), rule.enc
    n_days = len(enc.problem.day_windows)
    if n_days <= p.max:
        return
    activities = _counted(p, scoped_activities(enc.problem, instance.scope))
    by_day: dict[str, dict[int, list[int]]] = {}
    for a in activities:
        days: dict[int, list[int]] = defaultdict(list)
        for start in a.candidate_starts:
            day = enc.index.attribute(start, "day", None)
            if day is not None:
                days[day].append(start)
        by_day[a.id] = days
    for resource in scoped_resources(enc.problem, instance.scope):
        worked: list[IntVar | int] = []
        for day in range(n_days):
            lits: list[IntVar] = []
            for a in activities:
                lit = enc.assigned_at(a.id, resource.id, by_day[a.id].get(day, []), "exact")
                if not isinstance(lit, int):
                    lits.append(lit)
            if not lits:
                worked.append(0)
                continue
            w = enc.model.new_bool_var("")
            enc.model.add_max_equality(w, lits)
            worked.append(w)
        for i in range(n_days - p.max):
            run = worked[i : i + p.max + 1]
            rule.at_most(sum(run), p.max, sum(1 for w in run if not isinstance(w, int)))


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    n_days = len(ctx.problem.day_windows)
    counted = {a.id for a in _counted(p, scoped_activities(ctx.problem, instance.scope))}
    findings: list[Finding] = []
    for resource in scoped_resources(ctx.problem, instance.scope):
        worked: set[int] = set()
        for a in ctx.work(resource.id):
            if a.id in counted:
                day = ctx.index.attribute(ctx.placed[a.id].start, "day", None)
                if day is not None:
                    worked.add(day)
        for i in range(n_days - p.max):
            if all(d in worked for d in range(i, i + p.max + 1)):
                findings.append(
                    Finding(
                        1,
                        f"{text}: {resource.id} works days {i + 1}-{i + p.max + 1}",
                        (),
                        (resource.id,),
                    )
                )
    return findings


SPEC = TemplateSpec(
    "max_consecutive",
    1,
    Params,
    references=_references,
    encode=encode,
    check=check,
    explain=explain,
)
