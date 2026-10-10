from datetime import datetime
from typing import Annotated, Literal, Self
from uuid import UUID

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    StringConstraints,
    model_validator,
)

from cartlyf_api.examples import example_id
from cartlyf_engine.domain import Key
from cartlyf_engine.precheck import Issue

ImportKind = Literal["resources", "demands"]
ImportStatus = Literal["awaiting_file", "uploaded", "validated", "invalid", "committed"]
Filename = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=200)]


class ImportCreate(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "kind": "resources",
                    "resource_type_id": example_id("resource_type_id"),
                    "filename": "lecturers.csv",
                }
            ]
        },
    )

    kind: ImportKind
    resource_type_id: UUID | None = None
    schedule_id: UUID | None = None
    filename: Filename

    @model_validator(mode="after")
    def _target_fits_kind(self) -> Self:
        if (self.kind == "resources") != (self.resource_type_id is not None):
            raise ValueError("a resources import needs resource_type_id, and only it")
        if (self.kind == "demands") != (self.schedule_id is not None):
            raise ValueError("a demands import needs schedule_id, and only it")
        return self


class RowError(BaseModel):
    row: int
    column: str | None
    message: str


class ImportReport(BaseModel):
    valid: bool
    row_count: int
    created: int
    errors: list[RowError]
    error_count: int
    feasibility: list[Issue] = Field(default_factory=list[Issue])


class ImportResponse(BaseModel):
    id: UUID
    kind: ImportKind
    status: ImportStatus
    filename: str
    resource_type_id: UUID | None
    schedule_id: UUID | None
    columns: list[str] | None
    size_bytes: int | None
    report: ImportReport | None
    created_at: datetime
    committed_at: datetime | None


Column = Annotated[str, StringConstraints(min_length=1, max_length=200)]


class ResourceMapping(BaseModel):
    """CSV column for each resource field; attributes map attribute key -> column."""

    model_config = ConfigDict(extra="forbid")

    kind: Literal["resources"]
    code: Column
    name: Column
    tags: Column | None = None
    capacity: Column | None = None
    size: Column | None = None
    concurrency: Column | None = None
    attributes: dict[Key, Column] = Field(default_factory=dict[str, str])


class RequirementMapping(BaseModel):
    """One requirement per imported demand; *_column fields read per-row values."""

    model_config = ConfigDict(extra="forbid")

    role: Key
    resource_type_id: UUID | None = None
    count_min: NonNegativeInt = 1
    count_max: PositiveInt = 1
    hard: bool = True
    weight: NonNegativeInt = 0
    tags_column: Column | None = None
    fixed_codes_column: Column | None = None
    attribute_columns: dict[Key, Column] = Field(default_factory=dict[str, str])


class DemandMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    kind: Literal["demands"]
    demand_kind: Literal["session", "coverage"]
    slot_template_id: UUID
    name: Column
    sessions_per_week: Column | None = None
    duration_minutes: Column | None = None
    slot_labels: Column | None = None
    requirements: list[RequirementMapping] = Field(min_length=1, max_length=20)


class DryRunRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"mapping": {"kind": "resources", "code": "Code", "name": "Name"}}]
        },
    )

    mapping: Annotated[ResourceMapping | DemandMapping, Field(discriminator="kind")]
