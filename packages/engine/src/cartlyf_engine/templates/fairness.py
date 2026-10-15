from typing import cast

from pydantic import BaseModel, NonNegativeInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.templates.spec import References, TemplateSpec


class Params(Frozen):
    activity_filter: ActivityFilter
    lookback_days: NonNegativeInt


def _references(params: BaseModel) -> References:
    return References(series_ids=frozenset(cast(Params, params).activity_filter.series_ids))


SPEC = TemplateSpec("fairness", 1, Params, soft_only=True, whole_scope=True, references=_references)
