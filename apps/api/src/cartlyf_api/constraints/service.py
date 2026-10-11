from uuid import UUID, uuid4

from pydantic import JsonValue
from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities import repository as activities_repo
from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.constraints import repository as repo
from cartlyf_api.constraints.models import ConstraintInstanceRow
from cartlyf_api.constraints.references import as_uuids
from cartlyf_api.constraints.schemas import (
    ConstraintResponse,
    ConstraintWrite,
    ScopeWrite,
    TemplateResponse,
)
from cartlyf_api.errors import NotFound, Unprocessable, field_error
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.schedules.service import live_schedule
from cartlyf_engine.templates.registry import (
    REGISTRY,
    InvalidInstance,
    params_references,
    validate_instance,
)


def _response(row: ConstraintInstanceRow) -> ConstraintResponse:
    return ConstraintResponse(
        id=row.id,
        schedule_id=row.schedule_id,
        name=row.name,
        template_key=row.template_key,
        template_version=row.template_version,
        params=row.params,
        scope=ScopeWrite.model_validate(row.scope),
        hard=row.hard,
        weight=row.weight,
        enabled=row.enabled,
    )


async def _validated(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: ConstraintWrite
) -> dict[str, JsonValue]:
    org, scope = principal.organisation_id, body.scope
    if await resources_repo.missing_type_ids(session, org, set(scope.resource_type_ids)):
        raise NotFound("Unknown resource type")
    if await resources_repo.missing_resource_ids(session, org, set(scope.resource_ids)):
        raise NotFound("Unknown resource")
    if await activities_repo.missing_demand_ids(session, org, schedule_id, set(scope.series_ids)):
        raise NotFound("Unknown demand")
    try:
        params = validate_instance(
            body.template_key,
            body.template_version,
            body.params,
            hard=body.hard,
            weight=body.weight,
        )
    except InvalidInstance as exc:
        raise Unprocessable(
            [field_error(("body", *p.loc), p.msg, p.type) for p in exc.problems]
        ) from exc
    named = params_references(body.template_key, body.template_version, params)
    if await activities_repo.missing_demand_ids(
        session, org, schedule_id, as_uuids(named.series_ids)
    ):
        raise NotFound("Unknown demand")
    if await resources_repo.missing_resource_ids(session, org, as_uuids(named.resource_ids)):
        raise NotFound("Unknown resource")
    return params


def _row_values(body: ConstraintWrite, params: dict[str, JsonValue]) -> dict[str, object]:
    return {
        "name": body.name,
        "template_key": body.template_key,
        "template_version": body.template_version,
        "params": params,
        "scope": body.scope.model_dump(mode="json"),
        "hard": body.hard,
        "weight": body.weight,
        "enabled": body.enabled,
    }


async def _live(
    session: AsyncSession, principal: Principal, schedule_id: UUID, constraint_id: UUID
) -> ConstraintInstanceRow:
    row = await repo.get_constraint(session, principal.organisation_id, schedule_id, constraint_id)
    if row is None:
        raise NotFound("Unknown constraint instance")
    return row


async def create_constraint(
    session: AsyncSession, principal: Principal, schedule_id: UUID, body: ConstraintWrite
) -> ConstraintResponse:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    params = await _validated(session, principal, schedule_id, body)
    constraint_id = uuid4()
    await repo.insert_constraint(
        session,
        {
            "id": constraint_id,
            "organisation_id": principal.organisation_id,
            "schedule_id": schedule_id,
            **_row_values(body, params),
        },
    )
    await record_change(
        session,
        principal,
        "constraint.created",
        "constraint_instance",
        constraint_id,
        {"template": f"{body.template_key}@v{body.template_version}"},
    )
    return await get_constraint(session, principal, schedule_id, constraint_id)


async def replace_constraint(
    session: AsyncSession,
    principal: Principal,
    schedule_id: UUID,
    constraint_id: UUID,
    body: ConstraintWrite,
) -> ConstraintResponse:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    await _live(session, principal, schedule_id, constraint_id)
    params = await _validated(session, principal, schedule_id, body)
    await repo.update_constraint(
        session, principal.organisation_id, constraint_id, _row_values(body, params)
    )
    await record_change(
        session, principal, "constraint.updated", "constraint_instance", constraint_id
    )
    return await get_constraint(session, principal, schedule_id, constraint_id)


async def delete_constraint(
    session: AsyncSession, principal: Principal, schedule_id: UUID, constraint_id: UUID
) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    await live_schedule(session, principal, schedule_id)
    await _live(session, principal, schedule_id, constraint_id)
    await repo.update_constraint(
        session, principal.organisation_id, constraint_id, {"deleted_at": func.now()}
    )
    await record_change(
        session, principal, "constraint.deleted", "constraint_instance", constraint_id
    )


async def list_constraints(
    session: AsyncSession, principal: Principal, schedule_id: UUID
) -> list[ConstraintResponse]:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    rows = await repo.list_constraints(session, principal.organisation_id, schedule_id)
    return [_response(row) for row in rows]


async def get_constraint(
    session: AsyncSession, principal: Principal, schedule_id: UUID, constraint_id: UUID
) -> ConstraintResponse:
    principal.require(Permission.CONFIG_READ)
    await live_schedule(session, principal, schedule_id)
    return _response(await _live(session, principal, schedule_id, constraint_id))


def list_templates(principal: Principal) -> list[TemplateResponse]:
    principal.require(Permission.CONFIG_READ)
    return [
        TemplateResponse(
            key=spec.key,
            version=spec.version,
            soft_only=spec.soft_only,
            params_schema=spec.params_model.model_json_schema(),
        )
        for spec in sorted(REGISTRY.values(), key=lambda s: (s.key, s.version))
    ]
