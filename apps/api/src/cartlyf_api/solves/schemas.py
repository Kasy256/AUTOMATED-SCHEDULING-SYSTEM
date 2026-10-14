from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field

from cartlyf_api.db import JsonDict

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
