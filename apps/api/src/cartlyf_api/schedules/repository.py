from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import delete, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.schedules.models import Schedule, SlotTemplate


async def insert_schedule(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(Schedule).values(**values))


async def get_schedule(session: AsyncSession, org: UUID, schedule_id: UUID) -> Schedule | None:
    return await session.scalar(
        select(Schedule).where(
            Schedule.organisation_id == org,
            Schedule.id == schedule_id,
            Schedule.deleted_at.is_(None),
        )
    )


async def list_schedules(session: AsyncSession, org: UUID) -> Sequence[Schedule]:
    rows = await session.scalars(
        select(Schedule)
        .where(Schedule.organisation_id == org, Schedule.deleted_at.is_(None))
        .order_by(Schedule.start_date.desc(), Schedule.name, Schedule.id)
    )
    return rows.all()


async def update_schedule(
    session: AsyncSession, org: UUID, schedule_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(Schedule)
        .where(Schedule.organisation_id == org, Schedule.id == schedule_id)
        .values(**values, updated_at=func.now())
    )


async def insert_slot_template(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(SlotTemplate).values(**values))


async def get_slot_template(
    session: AsyncSession, org: UUID, schedule_id: UUID, slot_template_id: UUID
) -> SlotTemplate | None:
    return await session.scalar(
        select(SlotTemplate).where(
            SlotTemplate.organisation_id == org,
            SlotTemplate.schedule_id == schedule_id,
            SlotTemplate.id == slot_template_id,
        )
    )


async def slot_templates_for(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[SlotTemplate]:
    rows = await session.scalars(
        select(SlotTemplate)
        .where(SlotTemplate.organisation_id == org, SlotTemplate.schedule_id == schedule_id)
        .order_by(SlotTemplate.name, SlotTemplate.id)
    )
    return rows.all()


async def replace_slot_template(
    session: AsyncSession, org: UUID, slot_template_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(SlotTemplate)
        .where(SlotTemplate.organisation_id == org, SlotTemplate.id == slot_template_id)
        .values(**values, updated_at=func.now())
    )


async def delete_slot_template(session: AsyncSession, org: UUID, slot_template_id: UUID) -> None:
    await session.execute(
        delete(SlotTemplate).where(
            SlotTemplate.organisation_id == org, SlotTemplate.id == slot_template_id
        )
    )


async def slot_template_in_use(session: AsyncSession, org: UUID, slot_template_id: UUID) -> bool:
    used = await session.scalar(
        text(
            "SELECT EXISTS (SELECT 1 FROM demand WHERE organisation_id = :org "
            "AND slot_template_id = :id AND deleted_at IS NULL)"
        ),
        {"org": org, "id": slot_template_id},
    )
    return bool(used)
