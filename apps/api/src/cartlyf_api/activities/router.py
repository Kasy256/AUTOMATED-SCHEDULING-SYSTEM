from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from cartlyf_api.activities import activities, demands, pins
from cartlyf_api.activities.schemas import (
    ActivityResponse,
    ActivityWrite,
    DemandResponse,
    DemandWrite,
    PinResponse,
    PinWrite,
)
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["activities"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_ONE = {**_READ, 404: problem_response("Not found")}
_WRITE = {**_ONE, 409: problem_response("Conflict"), 422: problem_response("Invalid")}
_DEMANDS = "/schedules/{schedule_id}/demands"
_DEMAND = _DEMANDS + "/{demand_id}"
_ACTIVITIES = "/schedules/{schedule_id}/activities"
_ACTIVITY = _ACTIVITIES + "/{activity_id}"


@router.get(_DEMANDS, response_model=list[DemandResponse], responses=_ONE)
async def list_demands(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[DemandResponse]:
    return await demands.list_demands(session, principal, schedule_id)


@router.post(_DEMANDS, status_code=201, response_model=DemandResponse, responses=_WRITE)
async def create_demand(
    schedule_id: UUID, body: DemandWrite, session: DbSession, principal: CurrentPrincipal
) -> DemandResponse:
    return await demands.create_demand(session, principal, schedule_id, body)


@router.get(_DEMAND, response_model=DemandResponse, responses=_ONE)
async def get_demand(
    schedule_id: UUID, demand_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> DemandResponse:
    return await demands.get_demand(session, principal, schedule_id, demand_id)


@router.put(_DEMAND, response_model=DemandResponse, responses=_WRITE)
async def replace_demand(
    schedule_id: UUID,
    demand_id: UUID,
    body: DemandWrite,
    session: DbSession,
    principal: CurrentPrincipal,
) -> DemandResponse:
    return await demands.replace_demand(session, principal, schedule_id, demand_id, body)


@router.delete(_DEMAND, status_code=204, responses=_WRITE)
async def delete_demand(
    schedule_id: UUID, demand_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await demands.delete_demand(session, principal, schedule_id, demand_id)
    return Response(status_code=204)


@router.get(_ACTIVITIES, response_model=list[ActivityResponse], responses=_ONE)
async def list_activities(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[ActivityResponse]:
    return await activities.list_activities(session, principal, schedule_id)


@router.post(_ACTIVITIES, status_code=201, response_model=ActivityResponse, responses=_WRITE)
async def create_activity(
    schedule_id: UUID, body: ActivityWrite, session: DbSession, principal: CurrentPrincipal
) -> ActivityResponse:
    return await activities.create_activity(session, principal, schedule_id, body)


@router.get(_ACTIVITY, response_model=ActivityResponse, responses=_ONE)
async def get_activity(
    schedule_id: UUID, activity_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ActivityResponse:
    return await activities.get_activity(session, principal, schedule_id, activity_id)


@router.put(_ACTIVITY, response_model=ActivityResponse, responses=_WRITE)
async def replace_activity(
    schedule_id: UUID,
    activity_id: UUID,
    body: ActivityWrite,
    session: DbSession,
    principal: CurrentPrincipal,
) -> ActivityResponse:
    return await activities.replace_activity(session, principal, schedule_id, activity_id, body)


@router.delete(_ACTIVITY, status_code=204, responses=_WRITE)
async def delete_activity(
    schedule_id: UUID, activity_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await activities.delete_activity(session, principal, schedule_id, activity_id)
    return Response(status_code=204)


_PINS = "/schedules/{schedule_id}/pins"
_PIN = _PINS + "/{activity_id}"


@router.get(_PINS, response_model=list[PinResponse], responses=_ONE)
async def list_pins(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[PinResponse]:
    return await pins.list_pins(session, principal, schedule_id)


@router.put(_PIN, response_model=PinResponse, responses=_WRITE)
async def put_pin(
    schedule_id: UUID,
    activity_id: UUID,
    body: PinWrite,
    session: DbSession,
    principal: CurrentPrincipal,
) -> PinResponse:
    return await pins.put_pin(session, principal, schedule_id, activity_id, body)


@router.delete(_PIN, status_code=204, responses=_WRITE)
async def delete_pin(
    schedule_id: UUID, activity_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await pins.delete_pin(session, principal, schedule_id, activity_id)
    return Response(status_code=204)
