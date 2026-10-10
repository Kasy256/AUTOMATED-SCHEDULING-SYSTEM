from collections.abc import Mapping, Sequence
from uuid import UUID

from sqlalchemy import func, insert, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.imports.models import ImportJob


async def insert_job(session: AsyncSession, values: Mapping[str, object]) -> None:
    await session.execute(insert(ImportJob).values(**values))


async def get_job(session: AsyncSession, org: UUID, import_id: UUID) -> ImportJob | None:
    return await session.scalar(
        select(ImportJob).where(ImportJob.organisation_id == org, ImportJob.id == import_id)
    )


async def list_jobs(session: AsyncSession, org: UUID) -> Sequence[ImportJob]:
    rows = await session.scalars(
        select(ImportJob)
        .where(ImportJob.organisation_id == org)
        .order_by(ImportJob.created_at.desc(), ImportJob.id)
    )
    return rows.all()


async def update_job(
    session: AsyncSession, org: UUID, import_id: UUID, values: Mapping[str, object]
) -> None:
    await session.execute(
        update(ImportJob)
        .where(ImportJob.organisation_id == org, ImportJob.id == import_id)
        .values(**values, updated_at=func.now())
    )
