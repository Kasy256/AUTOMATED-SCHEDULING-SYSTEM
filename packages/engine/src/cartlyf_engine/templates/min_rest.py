from __future__ import annotations

from itertools import combinations
from typing import TYPE_CHECKING

from pydantic import PositiveInt

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntervalVar, IntVar

    from cartlyf_engine.encoding import Encoding, Rule


class Params(Frozen):
    minutes: PositiveInt


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def explain(instance: ConstraintInstance) -> str:
    return f"At least {_params(instance).minutes} minutes between a resource's activities"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    rest, enc = _params(instance).minutes, rule.enc
    activities = scoped_activities(enc.problem, instance.scope)
    for resource in scoped_resources(enc.problem, instance.scope):
        mine = [a for a in activities if (a.id, resource.id) in enc.uses]
        if rule.enforce is not None:
            # Intervals stretched by the rest time may not overlap: exactly "rest kept".
            stretched: list[IntervalVar] = []
            for a in mine:
                present = enc.conj(enc.uses[a.id, resource.id], rule.enforce, "exact")
                stretched.append(
                    enc.model.new_optional_fixed_size_interval_var(
                        enc.start[a.id], a.duration + rest, present, ""
                    )
                )
            if len(stretched) > 1:
                enc.model.add_no_overlap(stretched)
            continue
        for a, b in combinations(mine, 2):
            if _can_clash(a, b, rest):
                rule.penalize(_too_close(enc, resource.id, a, b, rest))


def _can_clash(a: Activity, b: Activity, rest: int) -> bool:
    return (
        min(b.candidate_starts) < max(a.candidate_starts) + a.duration + rest
        and min(a.candidate_starts) < max(b.candidate_starts) + b.duration + rest
    )


def _too_close(enc: Encoding, resource_id: str, a: Activity, b: Activity, rest: int) -> IntVar:
    """1 whenever both are on the resource less than `rest` apart; may over-count."""
    sa, sb = enc.start[a.id], enc.start[b.id]
    ua, ub = enc.uses[a.id, resource_id], enc.uses[b.id, resource_id]
    clash = enc.model.new_bool_var("")
    a_first = enc.model.new_bool_var("")
    enc.when(sb >= sa + a.duration + rest, ~clash, ua, ub, a_first)
    enc.when(sa >= sb + b.duration + rest, ~clash, ua, ub, ~a_first)
    return clash


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    rest, text = _params(instance).minutes, explain(instance)
    in_scope = {a.id for a in scoped_activities(ctx.problem, instance.scope)}
    findings: list[Finding] = []
    for resource in scoped_resources(ctx.problem, instance.scope):
        mine = [a for a in ctx.work(resource.id) if a.id in in_scope]
        for a, b in combinations(mine, 2):
            sa, sb = ctx.placed[a.id].start, ctx.placed[b.id].start
            if sb < sa + a.duration + rest and sa < sb + b.duration + rest:
                gap = sb - (sa + a.duration)
                findings.append(
                    Finding(
                        1,
                        f"{text}: {resource.id} has {gap} minutes between {a.id} and {b.id}",
                        (a.id, b.id),
                        (resource.id,),
                    )
                )
    return findings


SPEC = TemplateSpec("min_rest", 1, Params, encode=encode, check=check, explain=explain)
