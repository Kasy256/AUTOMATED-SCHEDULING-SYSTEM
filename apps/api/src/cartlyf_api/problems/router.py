from typing import Any
from uuid import UUID

from fastapi import APIRouter
from pydantic import BaseModel

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.auth.permissions import Permission
from cartlyf_api.errors import problem_response
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.tenancy import DbSession
from cartlyf_engine.precheck import Issue, precheck

router = APIRouter(tags=["problems"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_ONE: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
    404: problem_response("Not found"),
}


class FeasibilityResponse(BaseModel):
    problem_hash: str
    issues: list[Issue]


@router.get(
    "/schedules/{schedule_id}/feasibility", response_model=FeasibilityResponse, responses=_ONE
)
async def check_feasibility(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> FeasibilityResponse:
    principal.require(Permission.CONFIG_READ)
    snapshot = await build_snapshot(session, principal.organisation_id, schedule_id)
    return FeasibilityResponse(problem_hash=snapshot.hash, issues=precheck(snapshot.problem))
