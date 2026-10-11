from collections.abc import Sequence
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.schemas import RequirementSpec
from cartlyf_api.errors import NotFound
from cartlyf_api.resources import repository as resources_repo


async def check_requirement_refs(
    session: AsyncSession, org: UUID, requirements: Sequence[RequirementSpec]
) -> None:
    """404 for any referenced type/resource that is unknown, deleted or in another org."""
    type_ids = {r.resource_type_id for r in requirements if r.resource_type_id is not None}
    resource_ids = {i for r in requirements for i in r.fixed_resource_ids}
    if await resources_repo.missing_type_ids(session, org, type_ids):
        raise NotFound("Unknown resource type")
    if await resources_repo.missing_resource_ids(session, org, resource_ids):
        raise NotFound("Unknown resource")
