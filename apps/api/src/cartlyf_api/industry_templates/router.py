from typing import Any

from fastapi import APIRouter

from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.industry_templates import service
from cartlyf_api.industry_templates.schemas import IndustryTemplateDefinition
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["industry-templates"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_READ: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
}


@router.get("/industry-templates", response_model=list[IndustryTemplateDefinition], responses=_READ)
async def list_industry_templates(
    session: DbSession, principal: CurrentPrincipal
) -> list[IndustryTemplateDefinition]:
    return await service.list_templates(session, principal)
