from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.permissions import Role
from cartlyf_api.orgs.models import Membership, MembershipRole, Organisation


async def insert_organisation(
    session: AsyncSession, organisation_id: UUID, name: str, timezone: str
) -> None:
    await session.execute(
        insert(Organisation).values(id=organisation_id, name=name, timezone=timezone)
    )


async def get_organisation(session: AsyncSession, organisation_id: UUID) -> Organisation | None:
    return await session.scalar(
        select(Organisation).where(
            Organisation.id == organisation_id, Organisation.deleted_at.is_(None)
        )
    )


async def insert_membership(
    session: AsyncSession,
    *,
    membership_id: UUID,
    organisation_id: UUID,
    user_id: UUID,
    status: str,
) -> None:
    await session.execute(
        insert(Membership).values(
            id=membership_id, organisation_id=organisation_id, user_id=user_id, status=status
        )
    )


async def insert_roles(
    session: AsyncSession, organisation_id: UUID, membership_id: UUID, roles: Iterable[Role]
) -> None:
    await session.execute(
        insert(MembershipRole),
        [
            {"organisation_id": organisation_id, "membership_id": membership_id, "role": role}
            for role in roles
        ],
    )


def _active_membership(organisation_id: UUID, user_id: UUID) -> Select[UUID]:
    return select(Membership.id).where(
        Membership.organisation_id == organisation_id,
        Membership.user_id == user_id,
        Membership.status == "active",
        Membership.deleted_at.is_(None),
    )


async def is_active_member(session: AsyncSession, organisation_id: UUID, user_id: UUID) -> bool:
    return await session.scalar(_active_membership(organisation_id, user_id)) is not None


async def active_roles(
    session: AsyncSession, organisation_id: UUID, user_id: UUID
) -> frozenset[Role] | None:
    """Roles of an active member; None when not an active member. Needs org context."""
    membership_id = await session.scalar(_active_membership(organisation_id, user_id))
    if membership_id is None:
        return None
    roles = await session.scalars(
        select(MembershipRole.role).where(
            MembershipRole.organisation_id == organisation_id,
            MembershipRole.membership_id == membership_id,
        )
    )
    return frozenset(Role(role) for role in roles)


async def default_organisation(session: AsyncSession, user_id: UUID) -> UUID | None:
    return await session.scalar(
        select(Membership.organisation_id)
        .where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.deleted_at.is_(None),
        )
        .order_by(Membership.created_at, Membership.organisation_id)
        .limit(1)
    )
