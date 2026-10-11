from collections.abc import Mapping
from uuid import UUID

from sqlalchemy import insert
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.models import AuditLog
from cartlyf_api.auth.permissions import Principal


async def record_audit(
    session: AsyncSession,
    *,
    organisation_id: UUID,
    actor_user_id: UUID | None,
    action: str,
    target_type: str | None = None,
    target_id: UUID | None = None,
    details: Mapping[str, object] | None = None,
    via_platform_admin: bool = False,
) -> None:
    await session.execute(
        insert(AuditLog).values(
            organisation_id=organisation_id,
            actor_user_id=actor_user_id,
            action=action,
            target_type=target_type,
            target_id=target_id,
            details=dict(details or {}),
            via_platform_admin=via_platform_admin,
        )
    )


async def record_change(
    session: AsyncSession,
    principal: Principal,
    action: str,
    target_type: str,
    target_id: UUID,
    details: Mapping[str, object] | None = None,
) -> None:
    await record_audit(
        session,
        organisation_id=principal.organisation_id,
        actor_user_id=principal.user_id,
        action=action,
        target_type=target_type,
        target_id=target_id,
        details=details,
        via_platform_admin=principal.via_platform_admin,
    )
