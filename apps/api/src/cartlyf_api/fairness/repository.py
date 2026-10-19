from collections.abc import Collection, Mapping
from datetime import date
from uuid import UUID

from sqlalchemy import delete, func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.fairness.models import FairnessLedgerRow
from cartlyf_api.schedules.models import Schedule

LedgerKey = tuple[UUID, str, date]  # resource, counter, local day


async def delete_schedule_rows(session: AsyncSession, org: UUID, schedule_id: UUID) -> None:
    await session.execute(
        delete(FairnessLedgerRow).where(
            FairnessLedgerRow.organisation_id == org, FairnessLedgerRow.schedule_id == schedule_id
        )
    )


async def insert_rows(
    session: AsyncSession,
    org: UUID,
    schedule_id: UUID,
    version_id: UUID,
    counts: Mapping[LedgerKey, int],
) -> None:
    if not counts:
        return
    await session.execute(
        insert(FairnessLedgerRow),
        [
            {
                "organisation_id": org,
                "schedule_id": schedule_id,
                "version_id": version_id,
                "resource_id": resource_id,
                "counter": counter,
                "day": day,
                "count": count,
            }
            for (resource_id, counter, day), count in sorted(counts.items())
        ],
    )


async def totals(
    session: AsyncSession,
    org: UUID,
    *,
    exclude_schedule_id: UUID,
    counter: str,
    since: date,
    before: date,
    resource_ids: Collection[UUID],
) -> dict[UUID, int]:
    """Per-resource sum of a counter over [since, before), from live schedules but one."""
    rows = await session.execute(
        select(FairnessLedgerRow.resource_id, func.sum(FairnessLedgerRow.count))
        .join(
            Schedule,
            (Schedule.organisation_id == FairnessLedgerRow.organisation_id)
            & (Schedule.id == FairnessLedgerRow.schedule_id),
        )
        .where(
            FairnessLedgerRow.organisation_id == org,
            FairnessLedgerRow.counter == counter,
            FairnessLedgerRow.day >= since,
            FairnessLedgerRow.day < before,
            FairnessLedgerRow.schedule_id != exclude_schedule_id,
            FairnessLedgerRow.resource_id.in_(resource_ids),
            Schedule.deleted_at.is_(None),
        )
        .group_by(FairnessLedgerRow.resource_id)
    )
    return {resource_id: int(total) for resource_id, total in rows}
