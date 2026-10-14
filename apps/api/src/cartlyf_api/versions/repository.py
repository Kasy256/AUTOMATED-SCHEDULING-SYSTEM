from collections.abc import Collection, Sequence
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.models import Activity
from cartlyf_api.schedules.models import Schedule
from cartlyf_api.versions.diff import Placed
from cartlyf_api.versions.models import Assignment, AssignmentResource, SolutionVersion


async def list_versions(
    session: AsyncSession, org: UUID, schedule_id: UUID
) -> Sequence[SolutionVersion]:
    rows = await session.scalars(
        select(SolutionVersion)
        .where(SolutionVersion.organisation_id == org, SolutionVersion.schedule_id == schedule_id)
        .order_by(SolutionVersion.number.desc())
    )
    return rows.all()


async def get_version(session: AsyncSession, org: UUID, version_id: UUID) -> SolutionVersion | None:
    return await session.scalar(
        select(SolutionVersion).where(
            SolutionVersion.organisation_id == org, SolutionVersion.id == version_id
        )
    )


async def published_versions(
    session: AsyncSession, org: UUID
) -> Sequence[tuple[SolutionVersion, str]]:
    rows = await session.execute(
        select(SolutionVersion, Schedule.name)
        .join(
            Schedule,
            (Schedule.organisation_id == SolutionVersion.organisation_id)
            & (Schedule.id == SolutionVersion.schedule_id),
        )
        .where(
            SolutionVersion.organisation_id == org,
            SolutionVersion.status == "published",
            Schedule.deleted_at.is_(None),
        )
        .order_by(Schedule.name, SolutionVersion.number)
    )
    return [(version, name) for version, name in rows]


async def assignment_rows(
    session: AsyncSession,
    org: UUID,
    version_id: UUID,
    resource_ids: Collection[UUID] | None = None,
) -> Sequence[Assignment]:
    """Assignments of a version; with `resource_ids`, only those using any of them."""
    stmt = (
        select(Assignment)
        .where(Assignment.organisation_id == org, Assignment.version_id == version_id)
        .order_by(Assignment.start_at, Assignment.activity_id)
    )
    if resource_ids is not None:
        stmt = stmt.where(
            Assignment.activity_id.in_(
                select(AssignmentResource.activity_id).where(
                    AssignmentResource.organisation_id == org,
                    AssignmentResource.version_id == version_id,
                    AssignmentResource.resource_id.in_(resource_ids),
                )
            )
        )
    return (await session.scalars(stmt)).all()


async def resources_by_activity(
    session: AsyncSession, org: UUID, version_id: UUID
) -> dict[UUID, dict[str, list[UUID]]]:
    rows = await session.scalars(
        select(AssignmentResource)
        .where(
            AssignmentResource.organisation_id == org, AssignmentResource.version_id == version_id
        )
        .order_by(AssignmentResource.role, AssignmentResource.resource_id)
    )
    grouped: dict[UUID, dict[str, list[UUID]]] = {}
    for row in rows:
        grouped.setdefault(row.activity_id, {}).setdefault(row.role, []).append(row.resource_id)
    return grouped


async def activity_names(
    session: AsyncSession, org: UUID, activity_ids: Collection[UUID]
) -> dict[UUID, str]:
    if not activity_ids:
        return {}
    rows = await session.execute(
        select(Activity.id, Activity.name).where(
            Activity.organisation_id == org, Activity.id.in_(activity_ids)
        )
    )
    return {activity_id: name for activity_id, name in rows}


async def assignments_of(
    session: AsyncSession,
    org: UUID,
    version_id: UUID,
    resource_ids: Sequence[UUID] | None = None,
) -> dict[UUID, Placed]:
    rows = await assignment_rows(session, org, version_id, resource_ids)
    resources = await resources_by_activity(session, org, version_id)
    return {
        row.activity_id: (
            row.start_at,
            {role: frozenset(ids) for role, ids in resources.get(row.activity_id, {}).items()},
        )
        for row in rows
    }
