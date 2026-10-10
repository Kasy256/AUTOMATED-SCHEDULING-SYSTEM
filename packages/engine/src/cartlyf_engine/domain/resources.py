from typing import Literal

from pydantic import Field, PositiveInt

from cartlyf_engine.domain.base import Frozen, Id, Key, Tag
from cartlyf_engine.domain.filters import AttrValue, ResourceFilter, predicate_holds
from cartlyf_engine.domain.time import Window

ResourceKind = Literal["person", "space", "asset", "group"]


class Resource(Frozen):
    id: Id
    type_key: Key
    kind: ResourceKind
    tags: tuple[Tag, ...] = ()
    attrs: dict[str, AttrValue] = Field(default_factory=dict)
    capacity: PositiveInt | None = None
    size: PositiveInt | None = None
    concurrency: PositiveInt = 1
    unavailable: tuple[Window, ...] = ()
    preferred: tuple[Window, ...] = ()
    avoided: tuple[Window, ...] = ()


def resource_matches(resource: Resource, resource_filter: ResourceFilter) -> bool:
    if resource_filter.type_key is not None and resource.type_key != resource_filter.type_key:
        return False
    if not set(resource_filter.tags) <= set(resource.tags):
        return False
    return all(predicate_holds(resource.attrs, p) for p in resource_filter.attrs)
