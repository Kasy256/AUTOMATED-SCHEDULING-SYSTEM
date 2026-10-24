from __future__ import annotations

from typing import TYPE_CHECKING, Literal, Self

from pydantic import Field, JsonValue, NonNegativeInt, model_validator

from cartlyf_engine.checking import CheckContext, Finding
from cartlyf_engine.domain import ConstraintInstance
from cartlyf_engine.domain.base import Frozen, WindowKey
from cartlyf_engine.templates._load import (
    checked_loads,
    describe_limits,
    describe_load,
    encode_loads,
)
from cartlyf_engine.templates.spec import TemplateSpec

if TYPE_CHECKING:
    from cartlyf_engine.encoding import Rule


MINUTES: dict[str, JsonValue] = {"x-unit": "minutes"}


class Params(Frozen):
    period: Literal["day", "week", "horizon"] = Field(title="Period")
    window: WindowKey | None = Field(
        default=None,
        title="Part of day",
        description="Only count activities in this part of the day",
    )
    min_count: NonNegativeInt | None = Field(default=None, title="Min activities")
    min_minutes: NonNegativeInt | None = Field(
        default=None, title="Min time", json_schema_extra=MINUTES
    )

    @model_validator(mode="after")
    def _has_a_limit(self) -> Self:
        if self.min_count is None and self.min_minutes is None:
            raise ValueError("set min_count or min_minutes")
        return self


def _params(instance: ConstraintInstance) -> Params:
    return Params.model_validate(instance.params)


def explain(instance: ConstraintInstance) -> str:
    p = _params(instance)
    where = f" in '{p.window}'" if p.window else ""
    return f"At least {describe_limits(p.min_count, p.min_minutes)} per {p.period}{where}"


def relax(instance: ConstraintInstance) -> str:
    p = _params(instance)
    return f"Lower the minimum of {describe_limits(p.min_count, p.min_minutes)} per {p.period}"


def encode(rule: Rule, instance: ConstraintInstance) -> None:
    p = _params(instance)
    for load in encode_loads(rule, instance.scope, p.period, p.window, "under"):
        if p.min_count is not None:
            rule.at_least(load.count, p.min_count)
        if p.min_minutes is not None:
            rule.at_least(load.minutes, p.min_minutes)


def check(ctx: CheckContext, instance: ConstraintInstance) -> list[Finding]:
    p, text = _params(instance), explain(instance)
    findings: list[Finding] = []
    for load in checked_loads(ctx, instance.scope, p.period, p.window):
        counted, minutes = describe_load(load, p.period)
        if p.min_count is not None and load.count < p.min_count:
            findings.append(
                Finding(
                    p.min_count - load.count,
                    f"{text}: {counted}",
                    load.activity_ids,
                    (load.resource_id,),
                )
            )
        if p.min_minutes is not None and load.minutes < p.min_minutes:
            findings.append(
                Finding(
                    p.min_minutes - load.minutes,
                    f"{text}: {minutes}",
                    load.activity_ids,
                    (load.resource_id,),
                )
            )
    return findings


SPEC = TemplateSpec(
    "min_load",
    1,
    Params,
    encode=encode,
    check=check,
    explain=explain,
    relax=relax,
    title="Minimum workload",
    description="Ensures each resource does at least this much per period.",
)
