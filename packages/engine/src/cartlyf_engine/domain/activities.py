from itertools import pairwise
from typing import Self

from pydantic import Field, NonNegativeInt, PositiveInt, model_validator

from cartlyf_engine.domain.base import Frozen, Id, Key
from cartlyf_engine.domain.filters import ActivityFilter, AttrValue, ResourceFilter, predicate_holds


class Requirement(Frozen):
    role: Key
    filter: ResourceFilter = ResourceFilter()
    count_min: NonNegativeInt
    count_max: PositiveInt
    fixed_resource_ids: tuple[Id, ...] = ()
    hard: bool = True
    weight: NonNegativeInt = 0

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        if self.count_max < self.count_min:
            raise ValueError("count_max must be >= count_min")
        if len(set(self.fixed_resource_ids)) != len(self.fixed_resource_ids):
            raise ValueError("fixed_resource_ids must be distinct")
        if len(self.fixed_resource_ids) > self.count_max:
            raise ValueError("more fixed resources than count_max")
        if not self.hard and self.weight < 1:
            raise ValueError("a soft requirement needs weight >= 1")
        return self


class Pin(Frozen):
    start: NonNegativeInt | None = None
    resources: dict[Key, tuple[Id, ...]] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _not_empty(self) -> Self:
        if self.start is None and not self.resources:
            raise ValueError("a pin needs a start or resources")
        return self


class Activity(Frozen):
    id: Id
    series_id: Id | None = None
    duration: PositiveInt
    candidate_starts: tuple[NonNegativeInt, ...] = Field(min_length=1)
    requirements: tuple[Requirement, ...] = ()
    pinned: Pin | None = None
    attrs: dict[str, AttrValue] = Field(default_factory=dict)

    @model_validator(mode="after")
    def _consistent(self) -> Self:
        starts = self.candidate_starts
        if any(b <= a for a, b in pairwise(starts)):
            raise ValueError("candidate_starts must be strictly increasing")
        roles = [r.role for r in self.requirements]
        if len(set(roles)) != len(roles):
            raise ValueError("requirement roles must be unique")
        if self.pinned is not None:
            if self.pinned.start is not None and self.pinned.start not in starts:
                raise ValueError("pinned start is not a candidate start")
            if not set(self.pinned.resources) <= set(roles):
                raise ValueError("pinned role has no requirement")
        return self


def activity_matches(activity: Activity, activity_filter: ActivityFilter) -> bool:
    if activity_filter.series_ids and activity.series_id not in activity_filter.series_ids:
        return False
    return all(predicate_holds(activity.attrs, p) for p in activity_filter.attrs)
