from collections.abc import Iterable
from uuid import UUID

from sqlalchemy import Select, delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.models import AppUser
from cartlyf_api.auth.permissions import Role
from cartlyf_api.orgs.models import Membership, MembershipRole, Organisation
from cartlyf_api.orgs.schemas import MemberResponse


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


async def membership_summaries(session: AsyncSession, user_id: UUID) -> list[tuple[UUID, str]]:
    """The user's active organisations (visible through the self-read policies)."""
    rows = await session.execute(
        select(Organisation.id, Organisation.name)
        .join(Membership, Membership.organisation_id == Organisation.id)
        .where(
            Membership.user_id == user_id,
            Membership.status == "active",
            Membership.deleted_at.is_(None),
            Organisation.deleted_at.is_(None),
        )
        .order_by(Organisation.name, Organisation.id)
    )
    return [(row[0], row[1]) for row in rows]


async def get_membership(
    session: AsyncSession, organisation_id: UUID, membership_id: UUID, *, for_update: bool = False
) -> Membership | None:
    query = select(Membership).where(
        Membership.organisation_id == organisation_id,
        Membership.id == membership_id,
        Membership.deleted_at.is_(None),
    )
    return await session.scalar(query.with_for_update() if for_update else query)


async def membership_for_user(
    session: AsyncSession, organisation_id: UUID, user_id: UUID
) -> Membership | None:
    return await session.scalar(
        select(Membership).where(
            Membership.organisation_id == organisation_id,
            Membership.user_id == user_id,
            Membership.deleted_at.is_(None),
        )
    )


async def replace_roles(
    session: AsyncSession, organisation_id: UUID, membership_id: UUID, roles: Iterable[Role]
) -> None:
    await session.execute(
        delete(MembershipRole).where(
            MembershipRole.organisation_id == organisation_id,
            MembershipRole.membership_id == membership_id,
        )
    )
    await insert_roles(session, organisation_id, membership_id, roles)


async def count_active_org_admins(session: AsyncSession, organisation_id: UUID) -> int:
    count = await session.scalar(
        select(func.count())
        .select_from(MembershipRole)
        .join(
            Membership,
            (Membership.organisation_id == MembershipRole.organisation_id)
            & (Membership.id == MembershipRole.membership_id),
        )
        .where(
            MembershipRole.organisation_id == organisation_id,
            MembershipRole.role == Role.ORG_ADMIN,
            Membership.status == "active",
            Membership.deleted_at.is_(None),
        )
    )
    return count or 0


async def list_members(
    session: AsyncSession, organisation_id: UUID, membership_id: UUID | None = None
) -> list[MemberResponse]:
    query = (
        select(Membership, AppUser)
        .join(AppUser, AppUser.id == Membership.user_id)
        .where(Membership.organisation_id == organisation_id, Membership.deleted_at.is_(None))
        .order_by(AppUser.email)
    )
    if membership_id is not None:
        query = query.where(Membership.id == membership_id)
    rows = (await session.execute(query)).all()
    role_rows = await session.execute(
        select(MembershipRole.membership_id, MembershipRole.role).where(
            MembershipRole.organisation_id == organisation_id,
            MembershipRole.membership_id.in_([membership.id for membership, _ in rows]),
        )
    )
    roles: dict[UUID, list[Role]] = {}
    for member_id, role in role_rows:
        roles.setdefault(member_id, []).append(Role(role))
    return [
        MemberResponse(
            membership_id=membership.id,
            user_id=user.id,
            email=user.email,
            name=user.name,
            status=membership.status,
            roles=sorted(roles.get(membership.id, [])),
        )
        for membership, user in rows
    ]
