from typing import Annotated, Self
from uuid import UUID

from pydantic import (
    AfterValidator,
    AwareDatetime,
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from cartlyf_api.examples import example_id
from cartlyf_api.resources.attribute_schema import AttributeSchema
from cartlyf_api.resources.calendar import AvailabilityKind
from cartlyf_api.types import Code, Name
from cartlyf_engine.domain import Key, ResourceKind, Tag


def _distinct_sorted(tags: list[str]) -> list[str]:
    return sorted(set(tags))


Tags = Annotated[list[Tag], Field(max_length=100), AfterValidator(_distinct_sorted)]
Attributes = dict[str, JsonValue]


class ResourceTypeCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "key": "lecturer",
                    "name": "Lecturer",
                    "kind": "person",
                    "attribute_schema": {
                        "version": 1,
                        "attributes": [
                            {
                                "key": "employment",
                                "type": "enum",
                                "enum_values": ["full_time", "part_time"],
                            },
                        ],
                    },
                }
            ]
        },
    )

    key: Key
    name: Name
    kind: ResourceKind
    attribute_schema: AttributeSchema = Field(default_factory=AttributeSchema)


class ResourceTypeUpdate(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"name": "Lecturers"}]}
    )

    name: Name | None = None
    attribute_schema: AttributeSchema | None = None


class ResourceTypeResponse(BaseModel):
    id: UUID
    key: str
    name: str
    kind: ResourceKind
    attribute_schema: AttributeSchema


class ResourceCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "resource_type_id": example_id("resource_type_id"),
                    "code": "LEC-002",
                    "name": "Dr. A. Okello",
                    "tags": ["math101"],
                    "attributes": {"employment": "full_time"},
                }
            ]
        },
    )

    resource_type_id: UUID
    code: Code
    name: Name
    tags: Tags = Field(default_factory=list[str])
    attributes: Attributes = Field(default_factory=dict[str, JsonValue])
    capacity: PositiveInt | None = None
    size: PositiveInt | None = None
    concurrency: PositiveInt = 1


class ResourceUpdate(BaseModel):
    """Partial update: only fields present in the body change; null clears capacity/size."""

    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"name": "Dr. Okello"}]}
    )

    code: Code | None = None
    name: Name | None = None
    tags: Tags | None = None
    attributes: Attributes | None = None
    capacity: PositiveInt | None = None
    size: PositiveInt | None = None
    concurrency: PositiveInt | None = None


class ResourceResponse(BaseModel):
    id: UUID
    resource_type_id: UUID
    code: str
    name: str
    tags: list[str]
    attributes: Attributes
    capacity: int | None
    size: int | None
    concurrency: int


WeekdayNumber = Annotated[int, Field(ge=0, le=6, description="0 = Monday")]
DayMinute = Annotated[int, Field(ge=0, le=1439)]
EndMinute = Annotated[int, Field(ge=1, le=1440)]


class AvailabilityRuleCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {"kind": "unavailable", "weekday": 0, "start_minute": 480, "end_minute": 600}
            ]
        },
    )

    kind: AvailabilityKind
    weekday: WeekdayNumber
    start_minute: DayMinute
    end_minute: EndMinute

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.end_minute <= self.start_minute:
            raise ValueError("end_minute must be after start_minute")
        return self


class AvailabilityRuleResponse(AvailabilityRuleCreate):
    id: UUID
    resource_id: UUID


class AvailabilityExceptionCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "unavailable",
                    "starts_at": "2027-12-25T00:00:00+03:00",
                    "ends_at": "2027-12-26T00:00:00+03:00",
                    "reason": "Public holiday",
                }
            ]
        },
    )

    kind: AvailabilityKind
    starts_at: AwareDatetime
    ends_at: AwareDatetime
    reason: Annotated[str, StringConstraints(max_length=500)] | None = None

    @model_validator(mode="after")
    def _ordered(self) -> Self:
        if self.ends_at <= self.starts_at:
            raise ValueError("ends_at must be after starts_at")
        return self


class AvailabilityExceptionResponse(AvailabilityExceptionCreate):
    id: UUID
    resource_id: UUID
