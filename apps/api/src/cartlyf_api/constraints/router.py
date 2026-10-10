from typing import Any
from uuid import UUID

from fastapi import APIRouter, Response

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.constraints import service
from cartlyf_api.constraints.schemas import ConstraintResponse, ConstraintWrite, TemplateResponse
from cartlyf_api.errors import problem_response
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["constraints"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}
_ONE = {**_READ, 404: problem_response("Not found")}
_WRITE = {**_ONE, 409: problem_response("Conflict"), 422: problem_response("Invalid")}
_CONSTRAINTS = "/schedules/{schedule_id}/constraints"
_CONSTRAINT = _CONSTRAINTS + "/{constraint_instance_id}"


@router.get("/constraint-templates", response_model=list[TemplateResponse], responses=_READ)
async def list_constraint_templates(principal: CurrentPrincipal) -> list[TemplateResponse]:
    return service.list_templates(principal)


@router.get(_CONSTRAINTS, response_model=list[ConstraintResponse], responses=_ONE)
async def list_constraints(
    schedule_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[ConstraintResponse]:
    return await service.list_constraints(session, principal, schedule_id)


@router.post(_CONSTRAINTS, status_code=201, response_model=ConstraintResponse, responses=_WRITE)
async def create_constraint(
    schedule_id: UUID, body: ConstraintWrite, session: DbSession, principal: CurrentPrincipal
) -> ConstraintResponse:
    return await service.create_constraint(session, principal, schedule_id, body)


@router.get(_CONSTRAINT, response_model=ConstraintResponse, responses=_ONE)
async def get_constraint(
    schedule_id: UUID,
    constraint_instance_id: UUID,
    session: DbSession,
    principal: CurrentPrincipal,
) -> ConstraintResponse:
    return await service.get_constraint(session, principal, schedule_id, constraint_instance_id)


@router.put(_CONSTRAINT, response_model=ConstraintResponse, responses=_WRITE)
async def replace_constraint(
    schedule_id: UUID,
    constraint_instance_id: UUID,
    body: ConstraintWrite,
    session: DbSession,
    principal: CurrentPrincipal,
) -> ConstraintResponse:
    return await service.replace_constraint(
        session, principal, schedule_id, constraint_instance_id, body
    )


@router.delete(_CONSTRAINT, status_code=204, responses=_WRITE)
async def delete_constraint(
    schedule_id: UUID,
    constraint_instance_id: UUID,
    session: DbSession,
    principal: CurrentPrincipal,
) -> Response:
    await service.delete_constraint(session, principal, schedule_id, constraint_instance_id)
    return Response(status_code=204)
