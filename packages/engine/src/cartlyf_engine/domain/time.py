from typing import Self

from pydantic import NonNegativeInt, PositiveInt, model_validator

from cartlyf_engine.domain.base import Frozen


class Window(Frozen):
    """Half-open [start, end) in minutes from horizon start."""

    start: NonNegativeInt
    end: PositiveInt

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end <= self.start:
            raise ValueError("window end must be after start")
        return self
