from typing import Any
from uuid import UUID

from fastapi import APIRouter, Request
from fastapi.responses import StreamingResponse

from cartlyf_api.app_state import broker_of, engine_of, settings_of, solve_notifier_of
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.solves import service
from cartlyf_api.solves.events import run_events
from cartlyf_api.solves.schemas import RepairRequest, SolveRequest, SolveRunResponse
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["solves"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
    404: problem_response("Not found"),
}
_REQUEST = {
    **_READ,
    422: problem_response("Invalid"),
    429: problem_response("Too many solves running"),
    503: problem_response("Solve queue unavailable"),
}
_CANCEL = {**_READ, 409: problem_response("Run already finished")}


@router.post(
    "/schedules/{schedule_id}/solves",
    status_code=202,
    response_model=SolveRunResponse,
    responses=_REQUEST,
)
async def request_solve(
    schedule_id: UUID, body: SolveRequest, request: Request, principal: CurrentPrincipal
) -> SolveRunResponse:
    return await service.request_solve(
        engine_of(request), broker_of(request), settings_of(request), principal, schedule_id, body
    )


@router.post(
    "/schedules/{schedule_id}/repairs",
    status_code=202,
    response_model=SolveRunResponse,
    responses={**_REQUEST, 409: problem_response("Nothing published to repair")},
)
async def request_repair(
    schedule_id: UUID, body: RepairRequest, request: Request, principal: CurrentPrincipal
) -> SolveRunResponse:
    return await service.request_repair(
        engine_of(request), broker_of(request), settings_of(request), principal, schedule_id, body
    )


@router.get(
    "/schedules/{schedule_id}/solves", response_model=list[SolveRunResponse], responses=_READ
)
async def list_solves(
    schedule_id: UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> list[SolveRunResponse]:
    return await service.list_runs(session, settings_of(request), principal, schedule_id)


@router.get("/solves/{run_id}", response_model=SolveRunResponse, responses=_READ)
async def get_solve(
    run_id: UUID, request: Request, session: DbSession, principal: CurrentPrincipal
) -> SolveRunResponse:
    return await service.get_run(session, settings_of(request), principal, run_id)


@router.post(
    "/solves/{run_id}/cancel", status_code=202, response_model=SolveRunResponse, responses=_CANCEL
)
async def cancel_solve(
    run_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> SolveRunResponse:
    return await service.cancel_run(session, principal, run_id)


@router.get(
    "/solves/{run_id}/events",
    response_class=StreamingResponse,
    responses={**_READ, 200: {"content": {"text/event-stream": {}}}},
)
async def solve_events(
    run_id: UUID, request: Request, principal: CurrentPrincipal
) -> StreamingResponse:
    engine = engine_of(request)
    await service.require_run(engine, principal, run_id)
    return StreamingResponse(
        run_events(engine, solve_notifier_of(request), settings_of(request), principal, run_id),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-store", "X-Accel-Buffering": "no"},
    )
