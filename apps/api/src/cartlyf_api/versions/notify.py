from collections import defaultdict
from datetime import datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.versions import repository

_Placement = tuple[UUID, datetime, str, UUID]


async def _by_resource(
    session: AsyncSession, org: UUID, version_id: UUID | None
) -> dict[UUID, set[_Placement]]:
    grouped: dict[UUID, set[_Placement]] = defaultdict(set)
    if version_id is not None:
        for placement in await repository.placements(session, org, version_id):
            grouped[placement[3]].add(placement)
    return grouped


async def affected_users(
    session: AsyncSession, org: UUID, new_version_id: UUID, previous_version_id: UUID | None
) -> dict[UUID, int]:
    """Users whose own placements differ between the two versions -> their count in the new one."""
    new = await _by_resource(session, org, new_version_id)
    old = await _by_resource(session, org, previous_version_id)
    owners = await resources_repo.users_for_resources(session, org, new.keys() | old.keys())
    new_by_user: dict[UUID, set[_Placement]] = defaultdict(set)
    old_by_user: dict[UUID, set[_Placement]] = defaultdict(set)
    for resource_id, user_id in owners.items():
        new_by_user[user_id] |= new.get(resource_id, set())
        old_by_user[user_id] |= old.get(resource_id, set())
    return {
        user_id: len({activity for activity, *_ in placements})
        for user_id, placements in new_by_user.items()
        if placements != old_by_user[user_id]
    }
