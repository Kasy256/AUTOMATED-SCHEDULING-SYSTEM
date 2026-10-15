from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import AwareDatetime, BaseModel, ConfigDict, Field

from cartlyf_api.db import JsonDict
from cartlyf_engine.infeasibility import InfeasibilityReport

RunStatus = Literal[
    "queued",
    "running",
    "succeeded",
    "infeasible",
    "no_solution",
    "cancelled",
    "failed",
    "failed_verification",
]
ACTIVE: frozenset[str] = frozenset({"queued", "running"})


class SolveRequest(BaseModel):
    model_config = ConfigDict(
        extra="forbid", json_schema_extra={"examples": [{"time_limit_s": 30, "seed": 0}]}
    )

    time_limit_s: int | None = Field(None, ge=1)
    # CP-SAT's random_seed is an int32.
    seed: int = Field(0, ge=0, le=2**31 - 1)


class RepairRequest(SolveRequest):
    model_config = ConfigDict(
        extra="forbid",
        json_schema_extra={
            "examples": [{"freeze_before": "2027-01-13T00:00:00+03:00", "time_limit_s": 30}]
        },
    )

    # Assignments of the published version starting before this instant are kept as they are.
    freeze_before: AwareDatetime


class SolveRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    schedule_id: UUID
    status: RunStatus
    problem_hash: str
    progress: JsonDict
    conflicts: list[str]
    error: str | None
    version_id: UUID | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    kind: Literal["solve", "repair"]
    baseline_version_id: UUID | None
    freeze_before: datetime | None
    infeasibility: InfeasibilityReport | None
