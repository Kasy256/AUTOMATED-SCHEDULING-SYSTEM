from typing import Literal, cast

from pydantic import BaseModel, PositiveInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.templates.spec import References, TemplateSpec


class Params(Frozen):
    unit: Literal["days", "activities"]
    max: PositiveInt
    activity_filter: ActivityFilter | None = None


def _references(params: BaseModel) -> References:
    activity_filter = cast(Params, params).activity_filter
    return References(series_ids=frozenset(activity_filter.series_ids if activity_filter else ()))


SPEC = TemplateSpec("max_consecutive", 1, Params, references=_references)
