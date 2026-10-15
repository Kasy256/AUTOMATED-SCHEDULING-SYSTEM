from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from cartlyf_api.db import JsonDict
from cartlyf_api.examples import example_id

VersionStatus = Literal["draft", "published", "archived"]


class AssignmentOut(BaseModel):
    activity_id: UUID
    activity_name: str | None
    start_at: datetime
    end_at: datetime
    resources: dict[str, list[UUID]]


class VersionSummary(BaseModel):
    id: UUID
    schedule_id: UUID
    number: int
    status: VersionStatus
    solver_status: str
    hard_violations: int
    soft_total: int
    created_at: datetime
    published_at: datetime | None
    archived_at: datetime | None
    parent_version_id: UUID | None
    solve_run_id: UUID


class VersionDetail(VersionSummary):
    score: JsonDict
    assignments: list[AssignmentOut]


class AssignmentChange(BaseModel):
    activity_id: UUID
    before: AssignmentOut | None
    after: AssignmentOut | None


class VersionDiff(BaseModel):
    added: list[AssignmentChange]
    removed: list[AssignmentChange]
    moved: list[AssignmentChange]
    reassigned: list[AssignmentChange]


class MyAssignment(AssignmentOut):
    version_id: UUID
    schedule_id: UUID
    schedule_name: str
    roles: list[str]


class AssignmentEdit(BaseModel):
    """Place one activity; `resources` replaces its whole role -> resources map."""

    model_config = ConfigDict(extra="forbid")

    activity_id: UUID
    start_at: AwareDatetime
    resources: dict[str, list[UUID]]


class DraftRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [
                {
                    "changes": [
                        {
                            "activity_id": example_id("activity_id"),
                            "start_at": "2027-01-12T09:00:00+03:00",
                            "resources": {"lecturer": [example_id("resource_id")]},
                        }
                    ]
                }
            ]
        },
    )

    changes: list[AssignmentEdit] = Field(min_length=1)
