from typing import Annotated, cast

from pydantic import AfterValidator, BaseModel, Field

from cartlyf_engine.domain.base import Frozen, Id
from cartlyf_engine.templates.spec import References, TemplateSpec


def _distinct_pairable(group: tuple[str, ...]) -> tuple[str, ...]:
    if len(group) < 2 or len(set(group)) != len(group):
        raise ValueError("a link group needs at least two distinct series ids")
    return group


# Series ids, not activity ids: the i-th activity of each linked series starts together.
LinkGroup = Annotated[tuple[Id, ...], AfterValidator(_distinct_pairable)]


class Params(Frozen):
    link_groups: tuple[LinkGroup, ...] = Field(min_length=1)


def _references(params: BaseModel) -> References:
    groups = cast(Params, params).link_groups
    return References(series_ids=frozenset(s for group in groups for s in group))


SPEC = TemplateSpec("same_time", 1, Params, references=_references)
