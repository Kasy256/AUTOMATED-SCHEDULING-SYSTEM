from typing import Literal, Self

from pydantic import model_validator

from cartlyf_engine.domain.base import Frozen, Key
from cartlyf_engine.templates.spec import TemplateSpec


class Params(Frozen):
    headcount_from: Literal["group_sizes", "activity_attr"] = "group_sizes"
    headcount_attr: Key | None = None

    @model_validator(mode="after")
    def _attr_when_needed(self) -> Self:
        if (self.headcount_from == "activity_attr") != (self.headcount_attr is not None):
            raise ValueError(
                "headcount_attr is required exactly when headcount_from is activity_attr"
            )
        return self


SPEC = TemplateSpec("capacity_fit", 1, Params)
