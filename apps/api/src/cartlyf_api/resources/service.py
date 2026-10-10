from collections.abc import Mapping, Sequence
from typing import cast
from uuid import UUID, uuid4

from sqlalchemy import func
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal
from cartlyf_api.errors import Conflict, FieldError, NotFound, Unprocessable, field_error
from cartlyf_api.resources import repository as repo
from cartlyf_api.resources.attribute_schema import AttributeSchema, validate_attributes
from cartlyf_api.resources.models import Resource, ResourceType
from cartlyf_api.resources.schemas import (
    ResourceCreate,
    ResourceResponse,
    ResourceTypeCreate,
    ResourceTypeResponse,
    ResourceTypeUpdate,
    ResourceUpdate,
)
from cartlyf_engine.domain import ResourceKind

_NOT_NULLABLE = ("code", "name", "tags", "attributes", "concurrency")


def type_response(row: ResourceType) -> ResourceTypeResponse:
    return ResourceTypeResponse(
        id=row.id,
        key=row.key,
        name=row.name,
        kind=cast(ResourceKind, row.kind),  # the DB CHECK keeps it a ResourceKind
        attribute_schema=AttributeSchema.model_validate(row.attribute_schema),
    )


def resource_response(row: Resource) -> ResourceResponse:
    return ResourceResponse.model_validate(row, from_attributes=True)


def resource_errors(
    rtype: ResourceType,
    attributes: Mapping[str, object],
    capacity: int | None,
    size: int | None,
    loc_prefix: Sequence[str | int] = ("body",),
) -> list[FieldError]:
    schema = AttributeSchema.model_validate(rtype.attribute_schema)
    errors = validate_attributes(schema, attributes, (*loc_prefix, "attributes"))
    if capacity is not None and rtype.kind not in ("space", "asset"):
        errors.append(
            field_error((*loc_prefix, "capacity"), "capacity applies to space and asset resources")
        )
    if size is not None and rtype.kind != "group":
        errors.append(field_error((*loc_prefix, "size"), "size applies to group resources"))
    return errors


def resource_row(
    resource_id: UUID, organisation_id: UUID, body: ResourceCreate
) -> dict[str, object]:
    return {"id": resource_id, "organisation_id": organisation_id, **body.model_dump()}


async def _live_type(session: AsyncSession, principal: Principal, type_id: UUID) -> ResourceType:
    rtype = await repo.get_type(session, principal.organisation_id, type_id)
    if rtype is None:
        raise NotFound("Unknown resource type")
    return rtype


async def create_type(
    session: AsyncSession, principal: Principal, body: ResourceTypeCreate
) -> ResourceTypeResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    if await repo.type_key_in_use(session, org, body.key):
        raise Conflict(f"A resource type with key '{body.key}' already exists")
    type_id = uuid4()
    values = {"id": type_id, "organisation_id": org, **body.model_dump(mode="json")}
    await repo.insert_type(session, values)
    await record_change(session, principal, "resource_type.created", "resource_type", type_id)
    return ResourceTypeResponse(id=type_id, **body.model_dump())


async def list_types(session: AsyncSession, principal: Principal) -> list[ResourceTypeResponse]:
    principal.require(Permission.CONFIG_READ)
    return [type_response(t) for t in await repo.list_types(session, principal.organisation_id)]


async def get_type(
    session: AsyncSession, principal: Principal, type_id: UUID
) -> ResourceTypeResponse:
    principal.require(Permission.CONFIG_READ)
    return type_response(await _live_type(session, principal, type_id))


async def update_type(
    session: AsyncSession, principal: Principal, type_id: UUID, body: ResourceTypeUpdate
) -> ResourceTypeResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await _live_type(session, principal, type_id)
    values: dict[str, object] = {}
    if body.name is not None:
        values["name"] = body.name
    if body.attribute_schema is not None:
        misfits = [
            r.code
            for r in await repo.list_live_resources(session, org, type_id)
            if validate_attributes(body.attribute_schema, r.attributes, ())
        ]
        if misfits:
            raise Conflict(
                f"{len(misfits)} resources do not fit the new attribute schema, "
                f"e.g. {', '.join(misfits[:5])}"
            )
        values["attribute_schema"] = body.attribute_schema.model_dump(mode="json")
    if values:
        await repo.update_type(session, org, type_id, values)
        await record_change(
            session, principal, "resource_type.updated", "resource_type", type_id,
            {"fields": sorted(values)},
        )  # fmt: skip
    return type_response(await _live_type(session, principal, type_id))


async def delete_type(session: AsyncSession, principal: Principal, type_id: UUID) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await _live_type(session, principal, type_id)
    if await repo.type_in_use(session, org, type_id):
        raise Conflict("The resource type is still used by resources or requirements")
    await repo.update_type(session, org, type_id, {"deleted_at": func.now()})
    await record_change(session, principal, "resource_type.deleted", "resource_type", type_id)


async def create_resource(
    session: AsyncSession, principal: Principal, body: ResourceCreate
) -> ResourceResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    rtype = await _live_type(session, principal, body.resource_type_id)
    if errors := resource_errors(rtype, body.attributes, body.capacity, body.size):
        raise Unprocessable(errors)
    if body.code in await repo.live_codes(session, org):
        raise Conflict(f"A resource with code '{body.code}' already exists")
    resource_id = uuid4()
    await repo.insert_resources(session, [resource_row(resource_id, org, body)])
    await record_change(session, principal, "resource.created", "resource", resource_id)
    return ResourceResponse(id=resource_id, **body.model_dump())


async def _live_resource(
    session: AsyncSession, principal: Principal, resource_id: UUID
) -> Resource:
    row = await repo.get_resource(session, principal.organisation_id, resource_id)
    if row is None:
        raise NotFound("Unknown resource")
    return row


async def list_resources(session: AsyncSession, principal: Principal) -> list[ResourceResponse]:
    principal.require(Permission.CONFIG_READ)
    rows = await repo.list_live_resources(session, principal.organisation_id)
    return [resource_response(r) for r in rows]


async def get_resource(
    session: AsyncSession, principal: Principal, resource_id: UUID
) -> ResourceResponse:
    principal.require(Permission.CONFIG_READ)
    return resource_response(await _live_resource(session, principal, resource_id))


async def update_resource(
    session: AsyncSession, principal: Principal, resource_id: UUID, body: ResourceUpdate
) -> ResourceResponse:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    current = await _live_resource(session, principal, resource_id)
    changes = body.model_dump(exclude_unset=True)
    errors = [
        field_error(("body", name), "may not be null") for name in _NOT_NULLABLE
        if name in changes and changes[name] is None
    ]  # fmt: skip
    if errors:
        raise Unprocessable(errors)
    merged = resource_response(current).model_copy(update=changes)
    rtype = await repo.get_type(session, org, current.resource_type_id, include_deleted=True)
    if rtype is None:
        raise NotFound("Unknown resource type")
    if errors := resource_errors(rtype, merged.attributes, merged.capacity, merged.size):
        raise Unprocessable(errors)
    codes = await repo.live_codes(session, org)
    if codes.get(merged.code, resource_id) != resource_id:
        raise Conflict(f"A resource with code '{merged.code}' already exists")
    if changes:
        await repo.update_resource(session, org, resource_id, changes)
        await record_change(
            session, principal, "resource.updated", "resource", resource_id,
            {"fields": sorted(changes)},
        )  # fmt: skip
    return merged


async def delete_resource(session: AsyncSession, principal: Principal, resource_id: UUID) -> None:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await _live_resource(session, principal, resource_id)
    if await repo.resource_is_referenced(session, org, resource_id):
        raise Conflict("The resource is fixed on activities or pinned; remove those first")
    await repo.update_resource(session, org, resource_id, {"deleted_at": func.now()})
    await record_change(session, principal, "resource.deleted", "resource", resource_id)
