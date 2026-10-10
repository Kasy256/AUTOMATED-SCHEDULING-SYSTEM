from typing import Annotated
from uuid import UUID

from pydantic import AfterValidator, BaseModel, ConfigDict, Field, JsonValue, PositiveInt

from cartlyf_api.examples import example_id
from cartlyf_api.resources.attribute_schema import AttributeSchema
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
                            {"key": "employment", "type": "enum",
                             "enum_values": ["full_time", "part_time"]},
                        ],
                    },
                }
            ]
        },
    )  # fmt: skip

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
