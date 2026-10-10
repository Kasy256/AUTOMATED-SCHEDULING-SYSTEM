from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.constraints.models import ConstraintInstanceRow


async def insert_constraint(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(ConstraintInstanceRow).values(**values))


async def get_constraint(
    session: AsyncSession, org: UUID, schedule_id: UUID, constraint_id: UUID
) -> ConstraintInstanceRow | None:
    return await session.scalar(
        select(ConstraintInstanceRow).where(
            ConstraintInstanceRow.organisation_id == org,
            ConstraintInstanceRow.schedule_id == schedule_id,
            ConstraintInstanceRow.id == constraint_id,
            ConstraintInstanceRow.deleted_at.is_(None),
        )
    )


async def list_constraints(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[ConstraintInstanceRow]:
    rows = await session.scalars(
        select(ConstraintInstanceRow)
        .where(
            ConstraintInstanceRow.organisation_id == org,
            ConstraintInstanceRow.schedule_id == schedule_id,
            ConstraintInstanceRow.deleted_at.is_(None),
        )
        .order_by(ConstraintInstanceRow.name, ConstraintInstanceRow.id)
    )
    return rows.all()


async def enabled_for(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[ConstraintInstanceRow]:
    rows = await session.scalars(
        select(ConstraintInstanceRow)
        .where(
            ConstraintInstanceRow.organisation_id == org,
            ConstraintInstanceRow.schedule_id == schedule_id,
            ConstraintInstanceRow.deleted_at.is_(None),
            ConstraintInstanceRow.enabled.is_(True),
        )
        .order_by(ConstraintInstanceRow.id)
    )
    return rows.all()


async def update_constraint(
    session: AsyncSession, org: UUID, constraint_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(ConstraintInstanceRow)
        .where(
            ConstraintInstanceRow.organisation_id == org,
            ConstraintInstanceRow.id == constraint_id,
        )
        .values(**values, updated_at=func.now())
    )
