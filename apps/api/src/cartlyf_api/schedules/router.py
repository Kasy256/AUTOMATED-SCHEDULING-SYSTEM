from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.schedules import service
from cartlyf_api.schedules.schemas import (
    ScheduleCreate,
    ScheduleResponse,
    ScheduleUpdate,
    SlotTemplateResponse,
    SlotTemplateWrite,
)
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["schedules"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_ONE = {**_READ, 404: problem_response("Not found")}
_WRITE = {**_ONE, 409: problem_response("Conflict"), 422: problem_response("Invalid")}
_TEMPLATES = "/schedules/{schedule_id}/slot-templates"
_TEMPLATE = _TEMPLATES + "/{slot_template_id}"


@router.get("/schedules", response_model=list[ScheduleResponse], responses=_READ)
async def list_schedules(session: DbSession, principal: CurrentPrincipal) -> list[ScheduleResponse]:
    return await service.list_schedules(session, principal)


@router.post("/schedules", status_code=201, response_model=ScheduleResponse, responses=_WRITE)
async def create_schedule(
    body: ScheduleCreate, session: DbSession, principal: CurrentPrincipal
) -> ScheduleResponse:
    return await service.create_schedule(session, principal, body)


@router.get("/schedules/{schedule_id}", response_model=ScheduleResponse, responses=_ONE)
async def get_schedule(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ScheduleResponse:
    return await service.get_schedule(session, principal, schedule_id)


@router.patch("/schedules/{schedule_id}", response_model=ScheduleResponse, responses=_WRITE)
async def update_schedule(
    schedule_id: UUID, body: ScheduleUpdate, session: DbSession, principal: CurrentPrincipal
) -> ScheduleResponse:
    return await service.update_schedule(session, principal, schedule_id, body)


@router.delete("/schedules/{schedule_id}", status_code=204, responses=_WRITE)
async def delete_schedule(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await service.delete_schedule(session, principal, schedule_id)
    return Response(status_code=204)


@router.get(_TEMPLATES, response_model=list[SlotTemplateResponse], responses=_ONE)
async def list_slot_templates(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[SlotTemplateResponse]:
    return await service.list_slot_templates(session, principal, schedule_id)


@router.post(_TEMPLATES, status_code=201, response_model=SlotTemplateResponse, responses=_WRITE)
async def create_slot_template(
    schedule_id: UUID, body: SlotTemplateWrite, session: DbSession, principal: CurrentPrincipal
) -> SlotTemplateResponse:
    return await service.create_slot_template(session, principal, schedule_id, body)


@router.get(_TEMPLATE, response_model=SlotTemplateResponse, responses=_ONE)
async def get_slot_template(
    schedule_id: UUID, slot_template_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> SlotTemplateResponse:
    return await service.get_slot_template(session, principal, schedule_id, slot_template_id)


@router.put(_TEMPLATE, response_model=SlotTemplateResponse, responses=_WRITE)
async def replace_slot_template(
    schedule_id: UUID,
    slot_template_id: UUID,
    body: SlotTemplateWrite,
    session: DbSession,
    principal: CurrentPrincipal,
) -> SlotTemplateResponse:
    return await service.replace_slot_template(
        session, principal, schedule_id, slot_template_id, body
    )


@router.delete(_TEMPLATE, status_code=204, responses=_WRITE)
async def delete_slot_template(
    schedule_id: UUID, slot_template_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await service.delete_slot_template(session, principal, schedule_id, slot_template_id)
    return Response(status_code=204)
