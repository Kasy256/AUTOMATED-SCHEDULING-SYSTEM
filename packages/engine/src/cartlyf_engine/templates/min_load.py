from typing import Literal, Self

from pydantic import NonNegativeInt, model_validator

from cartlyf_engine.domain.base import Frozen, Key
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    period: Literal["day", "week", "horizon"]
    window: Key | None = None
    min_count: NonNegativeInt | None = None
    min_minutes: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _has_a_limit(self) -> Self:
        if self.min_count is None and self.min_minutes is None:
            raise ValueError("set min_count or min_minutes")
        return self


SPEC = TemplateSpec("min_load", 1, Params)
