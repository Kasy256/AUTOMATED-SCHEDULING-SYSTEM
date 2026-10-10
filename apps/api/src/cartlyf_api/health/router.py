import structlog
from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncEngine

from cartlyf_api.errors import problem, problem_response
from cartlyf_api.health.repository import fetch_db_role
from cartlyf_api.health.schemas import HealthResponse

router = APIRouter(tags=["health"])
log = structlog.get_logger()


@router.get(
    "/health",
    response_model=HealthResponse,
    responses={503: problem_response("Database unavailable or unsafe database role")},
)
async def health(request: Request) -> HealthResponse | JSONResponse:
    engine: AsyncEngine = request.app.state.db_engine
    try:
        role = await fetch_db_role(engine)
    except (SQLAlchemyError, OSError):
        log.warning("health_db_unavailable", exc_info=True)
        return problem(503, "Database unavailable")
    if not role.is_safe:
        # RLS is the tenant boundary; a superuser or BYPASSRLS connection silently disables it.
        log.error("health_unsafe_db_role", role=role.current_user)
        return problem(503, "Unsafe database role")
    return HealthResponse(status="ok", database=role)
