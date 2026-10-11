from typing import Self, cast

from pydantic import BaseModel, Field, NonNegativeInt, model_validator

from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.spec import References, TemplateSpec


class Pair(Frozen):
    before: Id
    after: Id

    @model_validator(mode="after")
    def _different(self) -> Self:
        if self.before == self.after:
            raise ValueError("before and after must differ")
        return self


class Params(Frozen):
    # Series ids: every activity of `before` ends min_gap minutes before any of `after` starts.
    pairs: tuple[Pair, ...] = Field(min_length=1)
    min_gap: NonNegativeInt = 0


def _references(params: BaseModel) -> References:
    pairs = cast(Params, params).pairs
    return References(series_ids=frozenset(s for p in pairs for s in (p.before, p.after)))


SPEC = TemplateSpec("precedence", 1, Params, references=_references)
