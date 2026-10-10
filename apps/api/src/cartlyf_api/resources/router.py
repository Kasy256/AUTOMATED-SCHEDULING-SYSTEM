from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.resources import availability, service
from cartlyf_api.resources.schemas import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionResponse,
    AvailabilityRuleCreate,
    AvailabilityRuleResponse,
    ResourceCreate,
    ResourceResponse,
    ResourceTypeCreate,
    ResourceTypeResponse,
    ResourceTypeUpdate,
    ResourceUpdate,
)
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["resources"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_ONE = {**_READ, 404: problem_response("Not found")}
_WRITE = {**_ONE, 409: problem_response("Conflict"), 422: problem_response("Invalid")}


@router.get("/resource-types", response_model=list[ResourceTypeResponse], responses=_READ)
async def list_resource_types(
    session: DbSession, principal: CurrentPrincipal
) -> list[ResourceTypeResponse]:
    return await service.list_types(session, principal)


@router.post(
    "/resource-types", status_code=201, response_model=ResourceTypeResponse, responses=_WRITE
)
async def create_resource_type(
    body: ResourceTypeCreate, session: DbSession, principal: CurrentPrincipal
) -> ResourceTypeResponse:
    return await service.create_type(session, principal, body)


@router.get(
    "/resource-types/{resource_type_id}", response_model=ResourceTypeResponse, responses=_ONE
)
async def get_resource_type(
    resource_type_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ResourceTypeResponse:
    return await service.get_type(session, principal, resource_type_id)


@router.patch(
    "/resource-types/{resource_type_id}", response_model=ResourceTypeResponse, responses=_WRITE
)
async def update_resource_type(
    resource_type_id: UUID,
    body: ResourceTypeUpdate,
    session: DbSession,
    principal: CurrentPrincipal,
) -> ResourceTypeResponse:
    return await service.update_type(session, principal, resource_type_id, body)


@router.delete("/resource-types/{resource_type_id}", status_code=204, responses=_WRITE)
async def delete_resource_type(
    resource_type_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await service.delete_type(session, principal, resource_type_id)
    return Response(status_code=204)


@router.get("/resources", response_model=list[ResourceResponse], responses=_READ)
async def list_resources(session: DbSession, principal: CurrentPrincipal) -> list[ResourceResponse]:
    return await service.list_resources(session, principal)


@router.post("/resources", status_code=201, response_model=ResourceResponse, responses=_WRITE)
async def create_resource(
    body: ResourceCreate, session: DbSession, principal: CurrentPrincipal
) -> ResourceResponse:
    return await service.create_resource(session, principal, body)


@router.get("/resources/{resource_id}", response_model=ResourceResponse, responses=_ONE)
async def get_resource(
    resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> ResourceResponse:
    return await service.get_resource(session, principal, resource_id)


@router.patch("/resources/{resource_id}", response_model=ResourceResponse, responses=_WRITE)
async def update_resource(
    resource_id: UUID, body: ResourceUpdate, session: DbSession, principal: CurrentPrincipal
) -> ResourceResponse:
    return await service.update_resource(session, principal, resource_id, body)


@router.delete("/resources/{resource_id}", status_code=204, responses=_WRITE)
async def delete_resource(
    resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await service.delete_resource(session, principal, resource_id)
    return Response(status_code=204)


_RULES = "/resources/{resource_id}/availability-rules"
_EXCEPTIONS = "/resources/{resource_id}/availability-exceptions"


@router.get(_RULES, response_model=list[AvailabilityRuleResponse], responses=_ONE)
async def list_availability_rules(
    resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[AvailabilityRuleResponse]:
    return await availability.list_rules(session, principal, resource_id)


@router.post(_RULES, status_code=201, response_model=AvailabilityRuleResponse, responses=_WRITE)
async def create_availability_rule(
    resource_id: UUID,
    body: AvailabilityRuleCreate,
    session: DbSession,
    principal: CurrentPrincipal,
) -> AvailabilityRuleResponse:
    return await availability.add_rule(session, principal, resource_id, body)


@router.delete(_RULES + "/{availability_rule_id}", status_code=204, responses=_WRITE)
async def delete_availability_rule(
    resource_id: UUID, availability_rule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await availability.delete_rule(session, principal, resource_id, availability_rule_id)
    return Response(status_code=204)


@router.get(_EXCEPTIONS, response_model=list[AvailabilityExceptionResponse], responses=_ONE)
async def list_availability_exceptions(
    resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[AvailabilityExceptionResponse]:
    return await availability.list_exceptions(session, principal, resource_id)


@router.post(
    _EXCEPTIONS, status_code=201, response_model=AvailabilityExceptionResponse, responses=_WRITE
)
async def create_availability_exception(
    resource_id: UUID,
    body: AvailabilityExceptionCreate,
    session: DbSession,
    principal: CurrentPrincipal,
) -> AvailabilityExceptionResponse:
    return await availability.add_exception(session, principal, resource_id, body)


@router.delete(_EXCEPTIONS + "/{availability_exception_id}", status_code=204, responses=_WRITE)
async def delete_availability_exception(
    resource_id: UUID,
    availability_exception_id: UUID,
    session: DbSession,
    principal: CurrentPrincipal,
) -> Response:
    await availability.delete_exception(session, principal, resource_id, availability_exception_id)
    return Response(status_code=204)
