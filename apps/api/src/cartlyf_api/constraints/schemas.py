from typing import Annotated
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    JsonValue,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
)

from cartlyf_api.examples import example_id
from cartlyf_api.types import Name
from cartlyf_engine.domain import AttributePredicate, Tag


class ScopeWrite(BaseModel):
    """What a rule applies to; empty means everything. series_ids are demand ids."""

    model_config = ConfigDict(extra="forbid")

    resource_type_ids: list[UUID] = Field(default_factory=list[UUID], max_length=50)
    tags: list[Tag] = Field(default_factory=list[str], max_length=50)
    attrs: list[AttributePredicate] = Field(default_factory=list[AttributePredicate], max_length=20)
    resource_ids: list[UUID] = Field(default_factory=list[UUID], max_length=1000)
    series_ids: list[UUID] = Field(default_factory=list[UUID], max_length=1000)


class ConstraintWrite(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "name": "Lecturers teach at most 2 sessions a day",
                    "template_key": "max_load",
                    "template_version": 1,
                    "params": {"period": "day", "max_count": 2},
                    "scope": {
                        "resource_type_ids": [example_id("resource_type_id")],
                        "series_ids": [example_id("demand_id")],
                    },
                    "hard": True,
                }
            ]
        },
    )

    name: Name
    template_key: Annotated[str, StringConstraints(min_length=1, max_length=100)]
    template_version: PositiveInt
    params: dict[str, JsonValue] = Field(default_factory=dict[str, JsonValue])
    scope: ScopeWrite = Field(default_factory=ScopeWrite)
    hard: bool
    weight: NonNegativeInt = 0
    enabled: bool = True


class ConstraintResponse(ConstraintWrite):
    id: UUID
    schedule_id: UUID


class TemplateResponse(BaseModel):
    key: str
    version: int
    soft_only: bool
    params_schema: dict[str, JsonValue]
