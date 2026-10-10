from uuid import UUID

from fastapi import APIRouter, Depends, Request

from cartlyf_api.app_state import settings_of
from cartlyf_api.auth.dependencies import Claims
from cartlyf_api.auth.schemas import TokenResponse
from cartlyf_api.errors import problem_response
from cartlyf_api.platform.service import start_platform_session
from cartlyf_api.rate_limit import rate_limit
from cartlyf_api.tenancy import DbSession

router = APIRouter(prefix="/platform", tags=["platform"])


@router.post(
    "/organisations/{organisation_id}/session",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("platform"))],
    responses={
        401: problem_response("Not authenticated"),
        404: problem_response("Not found"),
        429: problem_response("Too many attempts"),
    },
)
async def start_session(
    organisation_id: UUID, request: Request, session: DbSession, claims: Claims
) -> TokenResponse:
    return await start_platform_session(session, settings_of(request), claims, organisation_id)
