from typing import Any
from uuid import UUID

from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import StreamingResponse

from cartlyf_api.app_state import email_provider_of, engine_of, settings_of
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.email.outbox import deliver_all
from cartlyf_api.errors import problem_response
from cartlyf_api.tenancy import DbSession
from cartlyf_api.versions import editing, explain, service
from cartlyf_api.versions.schemas import (
    DraftRequest,
    ExplanationOut,
    MoveCheckOut,
    MoveRequest,
    MyAssignment,
    VersionDetail,
    VersionDiff,
    VersionSummary,
)

router = APIRouter(tags=["versions"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
    404: problem_response("Not found"),
}
_DIFF = {**_READ, 422: problem_response("Versions belong to different schedules")}
_DRAFT = {**_READ, 422: problem_response("The edit is invalid or breaks hard rules")}
_STATE = {**_READ, 409: problem_response("Not allowed in the version's current status")}
_MOVE = {**_READ, 422: problem_response("The move is malformed")}


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


@router.get("/solution-versions/{version_id}/export.csv", responses=_READ)
async def export_csv(
    version_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> StreamingResponse:
    filename, lines = await service.export_csv(session, principal, version_id)
    return StreamingResponse(
        lines,
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


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


@router.post(
    "/solution-versions/{version_id}/drafts",
    status_code=201,
    response_model=VersionDetail,
    responses=_DRAFT,
)
async def create_draft(
    request: Request,
    version_id: UUID,
    body: DraftRequest,
    session: DbSession,
    principal: CurrentPrincipal,
) -> VersionDetail:
    return await editing.create_draft(session, settings_of(request), principal, version_id, body)


@router.post(
    "/solution-versions/{version_id}/publish", response_model=VersionDetail, responses=_STATE
)
async def publish(
    request: Request,
    version_id: UUID,
    session: DbSession,
    principal: CurrentPrincipal,
    background: BackgroundTasks,
) -> VersionDetail:
    detail, queued = await editing.publish(session, settings_of(request), principal, version_id)
    if queued:
        background.add_task(deliver_all, engine_of(request), email_provider_of(request), queued)
    return detail


@router.post(
    "/solution-versions/{version_id}/archive", response_model=VersionDetail, responses=_STATE
)
async def archive(
    version_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> VersionDetail:
    return await editing.archive(session, principal, version_id)


@router.post(
    "/solution-versions/{version_id}/validate-move", response_model=MoveCheckOut, responses=_MOVE
)
async def validate_move(
    version_id: UUID, body: MoveRequest, session: DbSession, principal: CurrentPrincipal
) -> MoveCheckOut:
    return await explain.validate_move(session, principal, version_id, body)


@router.get(
    "/solution-versions/{version_id}/assignments/{activity_id}/explanation",
    response_model=ExplanationOut,
    responses=_READ,
)
async def explain_assignment(
    version_id: UUID, activity_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ExplanationOut:
    return await explain.explain(session, principal, version_id, activity_id)
