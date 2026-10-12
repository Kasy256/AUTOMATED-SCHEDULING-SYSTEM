from collections.abc import Collection, Mapping, Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import delete, func, insert, select, update
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.expansion import ActivityDraft
from cartlyf_api.activities.models import Activity, Demand, Pin, Requirement
from cartlyf_api.activities.schemas import RequirementSpec
from cartlyf_engine.domain import AttributePredicate


def requirement_rows(
    org: UUID, activity_id: UUID, specs: Sequence[RequirementSpec]
) -> list[dict[str, object]]:
    return [
        {
            "id": uuid4(),
            "organisation_id": org,
            "activity_id": activity_id,
            "position": position,
            "role": spec.role,
            "resource_type_id": spec.resource_type_id,
            "tags": sorted(set(spec.tags)),
            "attr_predicates": [p.model_dump(mode="json") for p in spec.attrs],
            "count_min": spec.count_min,
            "count_max": spec.count_max,
            "fixed_resource_ids": sorted(set(spec.fixed_resource_ids)),
            "hard": spec.hard,
            "weight": spec.weight,
        }
        for position, spec in enumerate(specs)
    ]


def requirement_spec(row: Requirement) -> RequirementSpec:
    return RequirementSpec(
        role=row.role,
        resource_type_id=row.resource_type_id,
        tags=row.tags,
        attrs=[AttributePredicate.model_validate(p) for p in row.attr_predicates],
        count_min=row.count_min,
        count_max=row.count_max,
        fixed_resource_ids=row.fixed_resource_ids,
        hard=row.hard,
        weight=row.weight,
    )


async def insert_demand(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(Demand).values(**values))


async def get_demand(
    session: AsyncSession, org: UUID, schedule_id: UUID, demand_id: UUID
) -> Demand | None:
    return await session.scalar(
        select(Demand).where(
            Demand.organisation_id == org,
            Demand.schedule_id == schedule_id,
            Demand.id == demand_id,
            Demand.deleted_at.is_(None),
        )
    )


async def live_demands(session: AsyncSession, org: UUID, schedule_id: UUID) -> Sequence[Demand]:
    rows = await session.scalars(
        select(Demand)
        .where(
            Demand.organisation_id == org,
            Demand.schedule_id == schedule_id,
            Demand.deleted_at.is_(None),
        )
        .order_by(Demand.name, Demand.id)
    )
    return rows.all()


async def demands_using(
    session: AsyncSession, org: UUID, slot_template_id: UUID
) -> Sequence[Demand]:
    rows = await session.scalars(
        select(Demand)
        .where(
            Demand.organisation_id == org,
            Demand.slot_template_id == slot_template_id,
            Demand.deleted_at.is_(None),
        )
        .order_by(Demand.name, Demand.id)
    )
    return rows.all()


async def update_demand(
    session: AsyncSession, org: UUID, demand_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(Demand)
        .where(Demand.organisation_id == org, Demand.id == demand_id)
        .values(**values, updated_at=func.now())
    )


async def missing_demand_ids(
    session: AsyncSession, org: UUID, schedule_id: UUID, ids: Collection[UUID]
) -> set[UUID]:
    if not ids:
        return set()
    found = await session.scalars(
        select(Demand.id).where(
            Demand.organisation_id == org,
            Demand.schedule_id == schedule_id,
            Demand.id.in_(ids),
            Demand.deleted_at.is_(None),
        )
    )
    return set(ids) - set(found)


async def activity_counts(
    session: AsyncSession, org: UUID, demand_ids: Collection[UUID]
) -> dict[UUID, int]:
    if not demand_ids:
        return {}
    rows = await session.execute(
        select(Activity.demand_id, func.count())
        .where(Activity.organisation_id == org, Activity.demand_id.in_(demand_ids))
        .group_by(Activity.demand_id)
    )
    return {demand_id: count for demand_id, count in rows if demand_id is not None}


async def insert_activities(
    session: AsyncSession,
    org: UUID,
    schedule_id: UUID,
    demand_id: UUID | None,
    drafts: Sequence[ActivityDraft],
) -> list[UUID]:
    if not drafts:
        return []
    ids = [uuid4() for _ in drafts]
    await session.execute(
        insert(Activity),
        [
            {
                "id": activity_id,
                "organisation_id": org,
                "schedule_id": schedule_id,
                "demand_id": demand_id,
                "series_id": demand_id,
                "natural_key": draft.key,
                "name": draft.name,
                "duration_minutes": draft.duration_minutes,
                "candidate_starts": list(draft.candidate_starts),
                "attrs": dict(draft.attrs),
            }
            for activity_id, draft in zip(ids, drafts, strict=True)
        ],
    )
    requirements = [
        row
        for activity_id, draft in zip(ids, drafts, strict=True)
        for row in requirement_rows(org, activity_id, draft.requirements)
    ]
    if requirements:
        await session.execute(insert(Requirement), requirements)
    return ids


async def demand_activities(
    session: AsyncSession, org: UUID, demand_id: UUID
) -> Sequence[Activity]:
    rows = await session.scalars(
        select(Activity).where(Activity.organisation_id == org, Activity.demand_id == demand_id)
    )
    return rows.all()


async def delete_activities(session: AsyncSession, org: UUID, ids: Collection[UUID]) -> None:
    """Requirements and pins cascade."""
    if ids:
        await session.execute(
            delete(Activity).where(Activity.organisation_id == org, Activity.id.in_(ids))
        )


async def delete_demand_activities(session: AsyncSession, org: UUID, demand_id: UUID) -> int:
    """Delete a demand's activities (requirements and pins cascade); returns pins removed."""
    pins = await session.scalar(
        select(func.count())
        .select_from(Pin)
        .join(
            Activity,
            (Activity.organisation_id == Pin.organisation_id) & (Activity.id == Pin.activity_id),
        )
        .where(Pin.organisation_id == org, Activity.demand_id == demand_id)
    )
    await session.execute(
        delete(Activity).where(Activity.organisation_id == org, Activity.demand_id == demand_id)
    )
    return pins or 0


async def list_activities(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[Activity]:
    rows = await session.scalars(
        select(Activity)
        .where(Activity.organisation_id == org, Activity.schedule_id == schedule_id)
        .order_by(Activity.name, Activity.id)
    )
    return rows.all()


async def manual_activities(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[Activity]:
    rows = await session.scalars(
        select(Activity).where(
            Activity.organisation_id == org,
            Activity.schedule_id == schedule_id,
            Activity.demand_id.is_(None),
        )
    )
    return rows.all()


async def get_activity(
    session: AsyncSession, org: UUID, schedule_id: UUID, activity_id: UUID
) -> Activity | None:
    return await session.scalar(
        select(Activity).where(
            Activity.organisation_id == org,
            Activity.schedule_id == schedule_id,
            Activity.id == activity_id,
        )
    )


async def requirements_for(
    session: AsyncSession, org: UUID, activity_ids: Collection[UUID]
) -> dict[UUID, list[Requirement]]:
    if not activity_ids:
        return {}
    rows = await session.scalars(
        select(Requirement)
        .where(Requirement.organisation_id == org, Requirement.activity_id.in_(activity_ids))
        .order_by(Requirement.activity_id, Requirement.position)
    )
    grouped: dict[UUID, list[Requirement]] = {}
    for row in rows:
        grouped.setdefault(row.activity_id, []).append(row)
    return grouped


async def replace_requirements(
    session: AsyncSession, org: UUID, activity_id: UUID, specs: Sequence[RequirementSpec]
) -> None:
    await session.execute(
        delete(Requirement).where(
            Requirement.organisation_id == org, Requirement.activity_id == activity_id
        )
    )
    rows = requirement_rows(org, activity_id, specs)
    if rows:
        await session.execute(insert(Requirement), rows)


async def update_activity(
    session: AsyncSession,
    org: UUID,
    activity_id: UUID,
    *,
    name: str,
    duration_minutes: int,
    candidate_starts: Sequence[datetime],
    attrs: Mapping[str, object],
) -> None:
    await session.execute(
        update(Activity)
        .where(Activity.organisation_id == org, Activity.id == activity_id)
        .values(
            name=name,
            duration_minutes=duration_minutes,
            candidate_starts=list(candidate_starts),
            attrs=dict(attrs),
        )
    )


async def delete_activity(session: AsyncSession, org: UUID, activity_id: UUID) -> None:
    await session.execute(
        delete(Activity).where(Activity.organisation_id == org, Activity.id == activity_id)
    )


async def upsert_pin(
    session: AsyncSession,
    org: UUID,
    schedule_id: UUID,
    activity_id: UUID,
    start_at: datetime | None,
    resources: Mapping[str, list[str]],
) -> None:
    statement = pg_insert(Pin).values(
        id=uuid4(),
        organisation_id=org,
        schedule_id=schedule_id,
        activity_id=activity_id,
        start_at=start_at,
        resources=dict(resources),
    )
    await session.execute(
        statement.on_conflict_do_update(
            constraint="pin_org_activity_key",
            set_={"start_at": start_at, "resources": dict(resources), "updated_at": func.now()},
        )
    )


async def pins_for(session: AsyncSession, org: UUID, schedule_id: UUID) -> dict[UUID, Pin]:
    rows = await session.scalars(
        select(Pin)
        .where(Pin.organisation_id == org, Pin.schedule_id == schedule_id)
        .order_by(Pin.activity_id)
    )
    return {row.activity_id: row for row in rows}


async def get_pin(session: AsyncSession, org: UUID, activity_id: UUID) -> Pin | None:
    return await session.scalar(
        select(Pin).where(Pin.organisation_id == org, Pin.activity_id == activity_id)
    )


async def delete_pin(session: AsyncSession, org: UUID, activity_id: UUID) -> bool:
    deleted = await session.scalars(
        delete(Pin)
        .where(Pin.organisation_id == org, Pin.activity_id == activity_id)
        .returning(Pin.id)
    )
    return deleted.first() is not None
