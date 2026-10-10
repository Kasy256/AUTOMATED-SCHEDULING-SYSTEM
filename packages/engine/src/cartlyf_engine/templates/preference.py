from typing import Literal, Self, cast

from pydantic import BaseModel, model_validator

from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.spec import References, TemplateSpec


class Pair(Frozen):
    resource_id: Id
    series_id: Id
    mode: Literal["prefer", "avoid"]


class Params(Frozen):
    source: Literal["calendar", "explicit"]
    pairs: tuple[Pair, ...] = ()

    @model_validator(mode="after")
    def _pairs_match_source(self) -> Self:
        if (self.source == "explicit") != bool(self.pairs):
            raise ValueError("pairs are required for explicit preferences and only for them")
        return self


def _references(params: BaseModel) -> References:
    pairs = cast(Params, params).pairs
    return References(
        series_ids=frozenset(p.series_id for p in pairs),
        resource_ids=frozenset(p.resource_id for p in pairs),
    )


SPEC = TemplateSpec("preference", 1, Params, soft_only=True, references=_references)
