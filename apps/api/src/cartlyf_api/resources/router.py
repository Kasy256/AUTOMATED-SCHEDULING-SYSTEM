from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.resources import service
from cartlyf_api.resources.schemas import (
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
