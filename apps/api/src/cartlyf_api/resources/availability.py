from datetime import UTC
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import NotFound
from cartlyf_api.resources import repository as repo
from cartlyf_api.resources.calendar import AvailabilityKind
from cartlyf_api.resources.models import AvailabilityException
from cartlyf_api.resources.schemas import (
    AvailabilityExceptionCreate,
    AvailabilityExceptionResponse,
    AvailabilityRuleCreate,
    AvailabilityRuleResponse,
)


async def _require_resource(session: AsyncSession, principal: Principal, resource_id: UUID) -> None:
    if await repo.get_resource(session, principal.organisation_id, resource_id) is None:
        raise NotFound("Unknown resource")


async def add_rule(
    session: AsyncSession, principal: Principal, resource_id: UUID, body: AvailabilityRuleCreate
) -> AvailabilityRuleResponse:
    principal.require(Permission.CONFIG_MANAGE)
    await _require_resource(session, principal, resource_id)
    rule_id = uuid4()
    await repo.insert_rule(
        session,
        {
            "id": rule_id,
            "organisation_id": principal.organisation_id,
            "resource_id": resource_id,
            **body.model_dump(),
        },
    )
    await record_change(
        session,
        principal,
        "availability_rule.created",
        "resource",
        resource_id,
        {"rule_id": str(rule_id)},
    )
    return AvailabilityRuleResponse(id=rule_id, resource_id=resource_id, **body.model_dump())


async def list_rules(
    session: AsyncSession, principal: Principal, resource_id: UUID
) -> list[AvailabilityRuleResponse]:
    principal.require(Permission.CONFIG_READ)
    await _require_resource(session, principal, resource_id)
    rows = (await repo.rules_for(session, principal.organisation_id, [resource_id])).get(
        resource_id, []
    )
    return [AvailabilityRuleResponse.model_validate(r, from_attributes=True) for r in rows]


async def delete_rule(
    session: AsyncSession, principal: Principal, resource_id: UUID, rule_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await _require_resource(session, principal, resource_id)
    if not await repo.delete_rule(session, principal.organisation_id, resource_id, rule_id):
        raise NotFound("Unknown availability rule")
    await record_change(
        session,
        principal,
        "availability_rule.deleted",
        "resource",
        resource_id,
        {"rule_id": str(rule_id)},
    )


def _exception_response(row: AvailabilityException) -> AvailabilityExceptionResponse:
    return AvailabilityExceptionResponse(
        id=row.id,
        resource_id=row.resource_id,
        kind=cast(AvailabilityKind, row.kind),
        starts_at=row.starts_at.astimezone(UTC),
        ends_at=row.ends_at.astimezone(UTC),
        reason=row.reason,
    )


async def add_exception(
    session: AsyncSession,
    principal: Principal,
    resource_id: UUID,
    body: AvailabilityExceptionCreate,
) -> AvailabilityExceptionResponse:
    principal.require(Permission.CONFIG_MANAGE)
    await _require_resource(session, principal, resource_id)
    exception_id = uuid4()
    await repo.insert_exception(
        session,
        {
            "id": exception_id,
            "organisation_id": principal.organisation_id,
            "resource_id": resource_id,
            **body.model_dump(),
        },
    )
    await record_change(
        session,
        principal,
        "availability_exception.created",
        "resource",
        resource_id,
        {"exception_id": str(exception_id)},
    )
    return AvailabilityExceptionResponse(
        id=exception_id,
        resource_id=resource_id,
        kind=body.kind,
        starts_at=body.starts_at.astimezone(UTC),
        ends_at=body.ends_at.astimezone(UTC),
        reason=body.reason,
    )


async def list_exceptions(
    session: AsyncSession, principal: Principal, resource_id: UUID
) -> list[AvailabilityExceptionResponse]:
    principal.require(Permission.CONFIG_READ)
    await _require_resource(session, principal, resource_id)
    found = await repo.exceptions_for(session, principal.organisation_id, [resource_id])
    return [_exception_response(row) for row in found.get(resource_id, [])]


async def delete_exception(
    session: AsyncSession, principal: Principal, resource_id: UUID, exception_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await _require_resource(session, principal, resource_id)
    if not await repo.delete_exception(
        session, principal.organisation_id, resource_id, exception_id
    ):
        raise NotFound("Unknown availability exception")
    await record_change(
        session,
        principal,
        "availability_exception.deleted",
        "resource",
        resource_id,
        {"exception_id": str(exception_id)},
    )
