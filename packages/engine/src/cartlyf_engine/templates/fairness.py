from pydantic import NonNegativeInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    activity_filter: ActivityFilter
    lookback_days: NonNegativeInt


SPEC = TemplateSpec("fairness", 1, Params, soft_only=True)
