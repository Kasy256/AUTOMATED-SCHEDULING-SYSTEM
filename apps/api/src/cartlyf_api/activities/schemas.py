from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    TypeAdapter,
    model_validator,
)

from cartlyf_api.examples import example_id
from cartlyf_api.types import Name
from cartlyf_engine.domain import AttributePredicate, AttrScalar, Key, Tag

ActivityAttrs = dict[Key, AttrScalar]


class RequirementSpec(BaseModel):
    """What one activity needs for one role; a role's resources must match all filters."""

    model_config = ConfigDict(extra="forbid")

    role: Key
    resource_type_id: UUID | None = None
    tags: list[Tag] = Field(default_factory=list[str], max_length=50)
    attrs: list[AttributePredicate] = Field(default_factory=list[AttributePredicate], max_length=20)
    count_min: NonNegativeInt = 1
    count_max: PositiveInt = 1
    fixed_resource_ids: list[UUID] = Field(default_factory=list[UUID], max_length=50)
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


def _unique_roles(requirements: list[RequirementSpec]) -> list[RequirementSpec]:
    roles = [r.role for r in requirements]
    if len(set(roles)) != len(roles):
        raise ValueError("requirement roles must be unique")
    return requirements


Requirements = Annotated[
    list[RequirementSpec], Field(min_length=1, max_length=20), AfterValidator(_unique_roles)
]
SlotLabels = Annotated[
    list[Annotated[str, Field(min_length=1, max_length=50)]], Field(min_length=1)
]


class SessionDemandSpec(BaseModel):
    """N sessions per week of the horizon (education)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["session"]
    sessions_per_week: Annotated[int, Field(ge=1, le=100)]
    duration_minutes: Annotated[int, Field(ge=1, le=1440)] | None = None
    slot_labels: SlotLabels | None = None
    requirements: Requirements
    attrs: ActivityAttrs = Field(default_factory=dict[str, AttrScalar])


class CoverageDemandSpec(BaseModel):
    """For every date x slot in the horizon, one activity needing these resources (rostering)."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["coverage"]
    slot_labels: SlotLabels | None = None
    requirements: Requirements
    attrs: ActivityAttrs = Field(default_factory=dict[str, AttrScalar])


DemandSpec = Annotated[SessionDemandSpec | CoverageDemandSpec, Field(discriminator="kind")]
DEMAND_SPEC: TypeAdapter[SessionDemandSpec | CoverageDemandSpec] = TypeAdapter(DemandSpec)


# Platform safety caps, not customer rules.
MAX_ACTIVITY_MINUTES = 7 * 1440
MAX_CANDIDATE_STARTS = 5000


class DemandWrite(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Calculus I",
                    "slot_template_id": example_id("slot_template_id"),
                    "spec": {
                        "kind": "session",
                        "sessions_per_week": 2,
                        "requirements": [
                            {
                                "role": "lecturer",
                                "resource_type_id": example_id("resource_type_id"),
                                "tags": ["math101"],
                            },
                            {"role": "group", "fixed_resource_ids": [example_id("resource_id")]},
                        ],
                    },
                }
            ]
        },
    )

    name: Name
    slot_template_id: UUID
    spec: DemandSpec


class DemandResponse(DemandWrite):
    id: UUID
    schedule_id: UUID
    activity_count: int


class ActivityWrite(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Staff meeting",
                    "duration_minutes": 60,
                    "candidate_starts": ["2027-01-11T09:00:00+03:00", "2027-01-12T09:00:00+03:00"],
                    "requirements": [
                        {
                            "role": "lecturer",
                            "resource_type_id": example_id("resource_type_id"),
                            "fixed_resource_ids": [example_id("resource_id")],
                        }
                    ],
                }
            ]
        },
    )

    name: Name
    duration_minutes: Annotated[int, Field(ge=1, le=MAX_ACTIVITY_MINUTES)]
    candidate_starts: Annotated[
        list[AwareDatetime], Field(min_length=1, max_length=MAX_CANDIDATE_STARTS)
    ]
    requirements: Annotated[
        list[RequirementSpec], Field(max_length=20), AfterValidator(_unique_roles)
    ] = Field(default_factory=list[RequirementSpec])
    attrs: ActivityAttrs = Field(default_factory=dict[str, AttrScalar])


class ActivityResponse(BaseModel):
    id: UUID
    schedule_id: UUID
    demand_id: UUID | None
    series_id: UUID | None
    name: str
    duration_minutes: int
    candidate_starts: list[datetime]
    requirements: list[RequirementSpec]
    attrs: ActivityAttrs


class PinWrite(BaseModel):
    """Lock an activity's start and/or some of its resources for future solves."""

    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "start_at": "2027-01-11T09:00:00+03:00",
                    "resources": {"lecturer": [example_id("resource_id")]},
                }
            ]
        },
    )

    start_at: AwareDatetime | None = None
    resources: dict[Key, list[UUID]] = Field(default_factory=dict[str, list[UUID]])


class PinResponse(BaseModel):
    activity_id: UUID
    start_at: datetime | None
    resources: dict[str, list[UUID]]
