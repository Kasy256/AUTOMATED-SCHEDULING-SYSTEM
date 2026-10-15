from collections.abc import Collection, Mapping, Sequence
from uuid import UUID

from sqlalchemy import delete, exists, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.resources.models import (
    AvailabilityException,
    AvailabilityRule,
    Resource,
    ResourceType,
)


async def insert_type(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(ResourceType).values(**values))


async def get_type(
    session: AsyncSession, org: UUID, type_id: UUID, *, include_deleted: bool = False
) -> ResourceType | None:
    query = select(ResourceType).where(
        ResourceType.organisation_id == org, ResourceType.id == type_id
    )
    if not include_deleted:
        query = query.where(ResourceType.deleted_at.is_(None))
    return await session.scalar(query)


async def list_types(session: AsyncSession, org: UUID) -> Sequence[ResourceType]:
    rows = await session.scalars(
        select(ResourceType)
        .where(ResourceType.organisation_id == org, ResourceType.deleted_at.is_(None))
        .order_by(ResourceType.name, ResourceType.id)
    )
    return rows.all()


async def types_by_id(session: AsyncSession, org: UUID) -> dict[UUID, ResourceType]:
    """Every type, deleted ones included: stored scopes and requirements may still name them."""
    rows = await session.scalars(select(ResourceType).where(ResourceType.organisation_id == org))
    return {row.id: row for row in rows}


async def type_key_in_use(session: AsyncSession, org: UUID, key: str) -> bool:
    return bool(
        await session.scalar(
            select(
                exists().where(
                    ResourceType.organisation_id == org,
                    ResourceType.key == key,
                    ResourceType.deleted_at.is_(None),
                )
            )
        )
    )


async def update_type(
    session: AsyncSession, org: UUID, type_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(ResourceType)
        .where(ResourceType.organisation_id == org, ResourceType.id == type_id)
        .values(**values, updated_at=func.now())
    )


async def type_in_use(session: AsyncSession, org: UUID, type_id: UUID) -> bool:
    used = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM resource WHERE organisation_id = :org "
            "AND resource_type_id = :id AND deleted_at IS NULL) "
            "OR EXISTS (SELECT 1 FROM requirement WHERE organisation_id = :org "
            "AND resource_type_id = :id)"
        ),
        {"org": org, "id": type_id},
    )
    return bool(used)


async def insert_resources(session: AsyncSession, rows: Sequence[Mapping[str, object]]) -> None:
    if rows:
        await session.execute(insert(Resource), [dict(row) for row in rows])


async def get_resource(session: AsyncSession, org: UUID, resource_id: UUID) -> Resource | None:
    return await session.scalar(
        select(Resource).where(
            Resource.organisation_id == org,
            Resource.id == resource_id,
            Resource.deleted_at.is_(None),
        )
    )


async def list_live_resources(
    session: AsyncSession, org: UUID, type_id: UUID | None = None
) -> Sequence[Resource]:
    query = select(Resource).where(Resource.organisation_id == org, Resource.deleted_at.is_(None))
    if type_id is not None:
        query = query.where(Resource.resource_type_id == type_id)
    return (await session.scalars(query.order_by(Resource.code, Resource.id))).all()


async def live_codes(session: AsyncSession, org: UUID) -> dict[str, UUID]:
    rows = await session.execute(
        select(Resource.code, Resource.id).where(
            Resource.organisation_id == org, Resource.deleted_at.is_(None)
        )
    )
    return {row[0]: row[1] for row in rows}


async def resource_ids_for_user(session: AsyncSession, org: UUID, user_id: UUID) -> list[UUID]:
    rows = await session.scalars(
        select(Resource.id).where(
            Resource.organisation_id == org,
            Resource.user_id == user_id,
            Resource.deleted_at.is_(None),
        )
    )
    return list(rows)


async def users_for_resources(
    session: AsyncSession, org: UUID, resource_ids: Collection[UUID]
) -> dict[UUID, UUID]:
    rows = await session.execute(
        select(Resource.id, Resource.user_id).where(
            Resource.organisation_id == org,
            Resource.id.in_(resource_ids),
            Resource.user_id.is_not(None),
            Resource.deleted_at.is_(None),
        )
    )
    return {rid: uid for rid, uid in rows if uid is not None}


async def update_resource(
    session: AsyncSession, org: UUID, resource_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(Resource)
        .where(Resource.organisation_id == org, Resource.id == resource_id)
        .values(**values, updated_at=func.now())
    )


async def resource_is_referenced(session: AsyncSession, org: UUID, resource_id: UUID) -> bool:
    used = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM requirement WHERE organisation_id = :org "
            "AND fixed_resource_ids @> ARRAY[CAST(:id AS uuid)]) "
            "OR EXISTS (SELECT 1 FROM pin p, jsonb_each(p.resources) r, "
            "jsonb_array_elements_text(r.value) v "
            "WHERE p.organisation_id = :org AND v.value = CAST(:id AS text))"
        ),
        {"org": org, "id": resource_id},
    )
    return bool(used)


async def missing_type_ids(session: AsyncSession, org: UUID, ids: Collection[UUID]) -> set[UUID]:
    if not ids:
        return set()
    found = await session.scalars(
        select(ResourceType.id).where(
            ResourceType.organisation_id == org,
            ResourceType.id.in_(ids),
            ResourceType.deleted_at.is_(None),
        )
    )
    return set(ids) - set(found)


async def missing_resource_ids(
    session: AsyncSession, org: UUID, ids: Collection[UUID]
) -> set[UUID]:
    if not ids:
        return set()
    found = await session.scalars(
        select(Resource.id).where(
            Resource.organisation_id == org, Resource.id.in_(ids), Resource.deleted_at.is_(None)
        )
    )
    return set(ids) - set(found)


async def insert_rule(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(AvailabilityRule).values(**values))


async def insert_exception(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(AvailabilityException).values(**values))


async def rules_for(
    session: AsyncSession, org: UUID, resource_ids: Collection[UUID]
) -> dict[UUID, list[AvailabilityRule]]:
    rows = await session.scalars(
        select(AvailabilityRule)
        .where(
            AvailabilityRule.organisation_id == org, AvailabilityRule.resource_id.in_(resource_ids)
        )
        .order_by(AvailabilityRule.weekday, AvailabilityRule.start_minute, AvailabilityRule.id)
    )
    grouped: dict[UUID, list[AvailabilityRule]] = {}
    for row in rows:
        grouped.setdefault(row.resource_id, []).append(row)
    return grouped


async def exceptions_for(
    session: AsyncSession, org: UUID, resource_ids: Collection[UUID]
) -> dict[UUID, list[AvailabilityException]]:
    rows = await session.scalars(
        select(AvailabilityException)
        .where(
            AvailabilityException.organisation_id == org,
            AvailabilityException.resource_id.in_(resource_ids),
        )
        .order_by(AvailabilityException.starts_at, AvailabilityException.id)
    )
    grouped: dict[UUID, list[AvailabilityException]] = {}
    for row in rows:
        grouped.setdefault(row.resource_id, []).append(row)
    return grouped


async def delete_rule(session: AsyncSession, org: UUID, resource_id: UUID, rule_id: UUID) -> bool:
    deleted = await session.scalars(
        delete(AvailabilityRule)
        .where(
            AvailabilityRule.organisation_id == org,
            AvailabilityRule.resource_id == resource_id,
            AvailabilityRule.id == rule_id,
        )
        .returning(AvailabilityRule.id)
    )
    return deleted.first() is not None


async def delete_exception(
    session: AsyncSession, org: UUID, resource_id: UUID, exception_id: UUID
) -> bool:
    deleted = await session.scalars(
        delete(AvailabilityException)
        .where(
            AvailabilityException.organisation_id == org,
            AvailabilityException.resource_id == resource_id,
            AvailabilityException.id == exception_id,
        )
        .returning(AvailabilityException.id)
    )
    return deleted.first() is not None
