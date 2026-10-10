from typing import Literal, Self

from pydantic import NonNegativeInt, model_validator

from cartlyf_engine.domain.base import Frozen, Key
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    period: Literal["day", "week", "horizon"]
    window: Key | None = None
    max_count: NonNegativeInt | None = None
    max_minutes: NonNegativeInt | None = None

    @model_validator(mode="after")
    def _has_a_limit(self) -> Self:
        if self.max_count is None and self.max_minutes is None:
            raise ValueError("set max_count or max_minutes")
        return self


SPEC = TemplateSpec("max_load", 1, Params)
