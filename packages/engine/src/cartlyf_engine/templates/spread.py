from __future__ import annotations

from collections import defaultdict
from typing import TYPE_CHECKING, Self

from pydantic import Field, PositiveInt, model_validator

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import Activity, ConstraintInstance
from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.index import ProblemIndex
from cartlyf_engine.templates.scope import scoped_activities, series_of
from cartlyf_engine.templates.spec import TemplateSpec
from cartlyf_engine.templates.text import count

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Rule


class Params(Frozen):
    max_per_day: PositiveInt | None = Field(default=None, title="Max per day")
    min_days_apart: PositiveInt | None = Field(default=None, title="Min days apart")

    @model_validator(mode="after")
    def _has_a_rule(self) -> Self:
        if self.max_per_day is None and self.min_days_apart is None:
            raise ValueError("set max_per_day or min_days_apart")
        return self


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def day_spans(n_days: int, k: int) -> list[range]:
    """Runs of k consecutive days; two activities fewer than k days apart share one."""
    return [range(i, min(i + k, n_days)) for i in range(max(1, n_days - k + 1))]


def _starts_by_day(index: ProblemIndex, activity: Activity) -> dict[int, list[int]]:
    by_day: dict[int, list[int]] = defaultdict(list)
    for start in activity.candidate_starts:
        day = index.attribute(start, "day", None)
        if day is not None:
            by_day[day].append(start)
    return by_day


def explain(instance: ConstraintInstance) -> str:
    p = _params(instance)
    parts: list[str] = []
    if p.max_per_day is not None:
        parts.append(f"at most {p.max_per_day} per day")
    if p.min_days_apart is not None:
        parts.append(f"at least {count(p.min_days_apart, 'day', 'days')} apart")
    return "Activities of a series: " + ", ".join(parts)


def relax(instance: ConstraintInstance) -> str:
    p = _params(instance)
    parts: list[str] = []
    if p.max_per_day is not None:
        parts.append(f"allow more than {p.max_per_day} per day")
    if p.min_days_apart is not None:
        parts.append(f"allow less than {count(p.min_days_apart, 'day', 'days')} apart")
    return " or ".join(parts).capitalize()


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p, enc = _params(instance), rule.enc
    n_days = len(enc.problem.day_windows)
    for series in series_of(scoped_activities(enc.problem, instance.scope)).values():
        days = [(a, _starts_by_day(enc.index, a)) for a in series]
        if p.max_per_day is not None:
            for day in range(n_days):
                on_day = [enc.bucket(a.id, by_day[day]) for a, by_day in days if day in by_day]
                rule.at_most(sum(on_day), p.max_per_day, len(on_day))
        if p.min_days_apart is not None:
            for span in day_spans(n_days, p.min_days_apart):
                within = [
                    enc.bucket(a.id, [s for d in span for s in by_day.get(d, ())])
                    for a, by_day in days
                    if any(d in by_day for d in span)
                ]
                rule.at_most(sum(within), 1, len(within))


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    n_days = len(ctx.problem.day_windows)
    findings: list[Finding] = []
    for series_id, series in series_of(scoped_activities(ctx.problem, instance.scope)).items():
        placed_on: dict[int, list[str]] = defaultdict(list)
        for activity in series:
            if activity.id in ctx.placed:
                day = ctx.index.attribute(ctx.placed[activity.id].start, "day", None)
                if day is not None:
                    placed_on[day].append(activity.id)
        if p.max_per_day is not None:
            for day, ids in sorted(placed_on.items()):
                if len(ids) > p.max_per_day:
                    findings.append(
                        Finding(
                            len(ids) - p.max_per_day,
                            f"{text}: series {series_id} has "
                            f"{count(len(ids), 'activity', 'activities')} on day {day + 1}",
                            tuple(ids),
                        )
                    )
        if p.min_days_apart is not None:
            for span in day_spans(n_days, p.min_days_apart):
                ids = [i for d in span for i in placed_on.get(d, [])]
                if len(ids) > 1:
                    findings.append(
                        Finding(
                            len(ids) - 1,
                            f"{text}: series {series_id} has "
                            f"{count(len(ids), 'activity', 'activities')} within days "
                            f"{span.start + 1}-{span.stop}",
                            tuple(ids),
                        )
                    )
    return findings


SPEC = TemplateSpec(
    "spread",
    1,
    Params,
    encode=encode,
    check=check,
    explain=explain,
    relax=relax,
    title="Spread across days",
    description="Spreads a demand's sessions over the days of the week.",
)
