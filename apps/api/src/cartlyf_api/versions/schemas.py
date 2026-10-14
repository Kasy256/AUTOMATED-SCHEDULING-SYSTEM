from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel

from cartlyf_api.db import JsonDict

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
