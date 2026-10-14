from typing import Any
from uuid import UUID

from fastapi import APIRouter

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.tenancy import DbSession
from cartlyf_api.versions import service
from cartlyf_api.versions.schemas import MyAssignment, VersionDetail, VersionDiff, VersionSummary

router = APIRouter(tags=["versions"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
    404: problem_response("Not found"),
}
_DIFF = {**_READ, 422: problem_response("Versions belong to different schedules")}


@router.get(
    "/schedules/{schedule_id}/versions", response_model=list[VersionSummary], responses=_READ
)
async def list_versions(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[VersionSummary]:
    return await service.list_versions(session, principal, schedule_id)


@router.get("/solution-versions/{version_id}", response_model=VersionDetail, responses=_READ)
async def get_version(
    version_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> VersionDetail:
    return await service.get_version(session, principal, version_id)


@router.get(
    "/solution-versions/{version_id}/diff/{other_version_id}",
    response_model=VersionDiff,
    responses=_DIFF,
)
async def diff_versions(
    version_id: UUID, other_version_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> VersionDiff:
    return await service.diff_versions(session, principal, version_id, other_version_id)


@router.get("/me/assignments", response_model=list[MyAssignment], responses=_READ)
async def my_assignments(session: DbSession, principal: CurrentPrincipal) -> list[MyAssignment]:
    return await service.my_assignments(session, principal)
