from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_audit
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.permissions import Permission, Principal, Role
from cartlyf_api.auth.tokens import INVITE_AUDIENCE, sign
from cartlyf_api.email import messages
from cartlyf_api.email.outbox import QueuedEmail, enqueue
from cartlyf_api.errors import Conflict, NotFound
from cartlyf_api.orgs import repository as repo
from cartlyf_api.orgs.schemas import InvitationRequest, MemberResponse
from cartlyf_api.settings import Settings

INVITE_LIFETIME = timedelta(days=7)


async def list_members(session: AsyncSession, principal: Principal) -> list[MemberResponse]:
    principal.require(Permission.MEMBERS_READ)
    return await repo.list_members(session, principal.organisation_id)


async def get_member(
    session: AsyncSession, principal: Principal, membership_id: UUID
) -> MemberResponse:
    principal.require(Permission.MEMBERS_READ)
    found = await repo.list_members(session, principal.organisation_id, membership_id)
    if not found:
        raise NotFound()
    return found[0]


async def set_roles(
    session: AsyncSession, principal: Principal, membership_id: UUID, roles: list[Role]
) -> MemberResponse:
    principal.require(Permission.MEMBERS_MANAGE)
    current = await get_member(session, principal, membership_id)
    if (
        Role.ORG_ADMIN in current.roles
        and Role.ORG_ADMIN not in roles
        and current.status == "active"
        and await repo.count_active_org_admins(session, principal.organisation_id) <= 1
    ):
        raise Conflict("An organisation needs at least one org admin")
    await repo.replace_roles(session, principal.organisation_id, membership_id, roles)
    await record_audit(
        session,
        organisation_id=principal.organisation_id,
        actor_user_id=principal.user_id,
        action="member.roles_changed",
        target_type="membership",
        target_id=membership_id,
        details={"from": list(current.roles), "to": list(roles)},
        via_platform_admin=principal.via_platform_admin,
    )
    return current.model_copy(update={"roles": roles})


async def invite(
    session: AsyncSession, settings: Settings, principal: Principal, request: InvitationRequest
) -> tuple[UUID, QueuedEmail]:
    """Create (or refresh) a pending membership and queue its invitation email."""
    principal.require(Permission.MEMBERS_MANAGE)
    org_id = principal.organisation_id
    user_id = await auth_repo.user_id_by_email(session, request.email)
    if user_id is None:
        user_id = uuid4()
        await auth_repo.insert_user(
            session,
            user_id=user_id,
            email=request.email,
            name=request.name,
            password_hash=None,
            email_verified=False,
        )
    membership = await repo.membership_for_user(session, org_id, user_id)
    if membership is not None and membership.status == "active":
        raise Conflict("Already a member of this organisation")
    if membership is None:
        membership_id = uuid4()
        await repo.insert_membership(
            session,
            membership_id=membership_id,
            organisation_id=org_id,
            user_id=user_id,
            status="invited",
        )
    else:
        membership_id = membership.id
    await repo.replace_roles(session, org_id, membership_id, request.roles)
    organisation = await repo.get_organisation(session, org_id)
    assert organisation is not None
    token = sign(
        settings.jwt_secret.get_secret_value(),
        INVITE_AUDIENCE,
        {"sub": str(user_id), "org": str(org_id), "mid": str(membership_id)},
        INVITE_LIFETIME,
        datetime.now(UTC),
    )
    message = messages.invitation(settings, request.email, organisation.name, token)
    queued = await enqueue(session, user_id, message)
    await record_audit(
        session,
        organisation_id=org_id,
        actor_user_id=principal.user_id,
        action="member.invited",
        target_type="membership",
        target_id=membership_id,
        details={"roles": list(request.roles)},
        via_platform_admin=principal.via_platform_admin,
    )
    return membership_id, queued
