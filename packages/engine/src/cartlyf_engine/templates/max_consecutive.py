from typing import Literal

from pydantic import PositiveInt

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.domain.filters import ActivityFilter
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    unit: Literal["days", "activities"]
    max: PositiveInt
    activity_filter: ActivityFilter | None = None


SPEC = TemplateSpec("max_consecutive", 1, Params)
