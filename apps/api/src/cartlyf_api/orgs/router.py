from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request

from cartlyf_api.app_state import email_provider_of, engine_of, settings_of
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.email.outbox import deliver
from cartlyf_api.errors import problem_response
from cartlyf_api.orgs import service
from cartlyf_api.orgs.schemas import (
    InvitationRequest,
    InvitationResponse,
    MemberResponse,
    RolesUpdate,
)
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["members"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_ERRORS: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_NOT_FOUND: dict[int | str, dict[str, Any]] = {404: problem_response("No such member")}


@router.get("/members", response_model=list[MemberResponse], responses=_ERRORS)
async def list_members(session: DbSession, principal: CurrentPrincipal) -> list[MemberResponse]:
    return await service.list_members(session, principal)


@router.get(
    "/members/{membership_id}",
    response_model=MemberResponse,
    responses={**_ERRORS, **_NOT_FOUND},
)
async def get_member(
    membership_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> MemberResponse:
    return await service.get_member(session, principal, membership_id)


@router.put(
    "/members/{membership_id}/roles",
    response_model=MemberResponse,
    responses={**_ERRORS, **_NOT_FOUND, 409: problem_response("Would remove the last org admin")},
)
async def set_member_roles(
    membership_id: UUID, body: RolesUpdate, session: DbSession, principal: CurrentPrincipal
) -> MemberResponse:
    return await service.set_roles(session, principal, membership_id, body.roles)


@router.post(
    "/invitations",
    status_code=201,
    response_model=InvitationResponse,
    responses={**_ERRORS, 409: problem_response("Already a member")},
)
async def create_invitation(
    request: Request,
    body: InvitationRequest,
    session: DbSession,
    principal: CurrentPrincipal,
    background: BackgroundTasks,
) -> InvitationResponse:
    membership_id, queued = await service.invite(session, settings_of(request), principal, body)
    background.add_task(deliver, engine_of(request), email_provider_of(request), queued)
    return InvitationResponse(membership_id=membership_id)
