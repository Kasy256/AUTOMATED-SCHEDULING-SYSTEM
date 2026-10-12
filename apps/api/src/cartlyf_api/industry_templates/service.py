from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import NotFound
from cartlyf_api.industry_templates import repository as repo
from cartlyf_api.industry_templates.schemas import IndustryTemplateDefinition


async def list_templates(
    session: AsyncSession, principal: Principal
) -> list[IndustryTemplateDefinition]:
    principal.require(Permission.CONFIG_READ)
    rows = await repo.latest_templates(session)
    return [IndustryTemplateDefinition.model_validate(row.definition) for row in rows]


async def get_template(session: AsyncSession, key: str) -> IndustryTemplateDefinition:
    row = await repo.latest_template(session, key)
    if row is None:
        raise NotFound("Unknown industry template")
    return IndustryTemplateDefinition.model_validate(row.definition)
