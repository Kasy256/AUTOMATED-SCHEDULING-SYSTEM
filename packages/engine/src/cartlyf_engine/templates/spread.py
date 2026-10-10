from typing import Self

from pydantic import PositiveInt, model_validator

from cartlyf_engine.domain.base import Frozen
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    max_per_day: PositiveInt | None = None
    min_days_apart: PositiveInt | None = None

    @model_validator(mode="after")
    def _has_a_rule(self) -> Self:
        if self.max_per_day is None and self.min_days_apart is None:
            raise ValueError("set max_per_day or min_days_apart")
        return self


SPEC = TemplateSpec("spread", 1, Params)
