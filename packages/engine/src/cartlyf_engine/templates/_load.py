"""Load per resource per period, shared by max_load and min_load (same shape, opposite bound)."""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from typing import TYPE_CHECKING

from cartlyf_engine.checking import CheckContext
from cartlyf_engine.domain import Scope
from cartlyf_engine.index import Period
from cartlyf_engine.templates.scope import scoped_activities, scoped_resources
from cartlyf_engine.templates.text import count

if TYPE_CHECKING:
    from ortools.sat.python.cp_model import IntVar

    from cartlyf_engine.encoding import Expr, Rule


@dataclass(frozen=True)
class LoadExpr:
    resource_id: str
    period: int
    count: Expr
    count_upper: int
    minutes: Expr
    minutes_upper: int


@dataclass(frozen=True)
class Load:
    resource_id: str
    period: int
    count: int
    minutes: int
    activity_ids: tuple[str, ...]


def describe_limits(count_limit: int | None, minutes_limit: int | None) -> str:
    parts: list[str] = []
    if count_limit is not None:
        parts.append(count(count_limit, "activity", "activities"))
    if minutes_limit is not None:
        parts.append(f"{minutes_limit} minutes")
    return " and ".join(parts)


def describe_load(load: Load, period: Period) -> tuple[str, str]:
    where = f"in {period} {load.period + 1}"
    return (
        f"{load.resource_id} has {count(load.count, 'activity', 'activities')} {where}",
        f"{load.resource_id} has {load.minutes} minutes {where}",
    )


def encode_loads(rule: Rule, scope: Scope, period: Period, window: str | None) -> list[LoadExpr]:
    enc = rule.enc
    activities = scoped_activities(enc.problem, scope)
    n = len(enc.index.periods(period))
    loads: list[LoadExpr] = []
    for resource in scoped_resources(enc.problem, scope):
        buckets: list[list[tuple[int, IntVar]]] = [[] for _ in range(n)]
        for activity in activities:
            if resource.id not in enc.index.candidates(activity.id):
                continue
            by_period: dict[int, list[int]] = defaultdict(list)
            for start in activity.candidate_starts:
                p = enc.index.attribute(start, period, window)
                if p is not None:
                    by_period[p].append(start)
            for p, starts in by_period.items():
                lit = enc.assigned_at(activity.id, resource.id, starts, "exact")
                if not isinstance(lit, int):
                    buckets[p].append((activity.duration, lit))
        for p, items in enumerate(buckets):
            loads.append(
                LoadExpr(
                    resource.id,
                    p,
                    sum(lit for _, lit in items),
                    len(items),
                    sum(d * lit for d, lit in items),
                    sum(d for d, _ in items),
                )
            )
    return loads


def checked_loads(
    ctx: CheckContext, scope: Scope, period: Period, window: str | None
) -> list[Load]:
    in_scope = {a.id for a in scoped_activities(ctx.problem, scope)}
    n = len(ctx.index.periods(period))
    loads: list[Load] = []
    for resource in scoped_resources(ctx.problem, scope):
        counted: list[list[tuple[str, int]]] = [[] for _ in range(n)]
        for activity in ctx.work(resource.id):
            if activity.id not in in_scope:
                continue
            p = ctx.index.attribute(ctx.placed[activity.id].start, period, window)
            if p is not None:
                counted[p].append((activity.id, activity.duration))
        loads += [
            Load(resource.id, p, len(items), sum(d for _, d in items), tuple(i for i, _ in items))
            for p, items in enumerate(counted)
        ]
    return loads
