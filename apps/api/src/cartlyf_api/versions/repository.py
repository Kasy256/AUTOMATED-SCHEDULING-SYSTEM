from collections.abc import Collection, Sequence
from datetime import datetime
from uuid import UUID

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.activities.models import Activity
from cartlyf_api.resources.models import Resource
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


async def get_version(
    session: AsyncSession, org: UUID, version_id: UUID, *, for_update: bool = False
) -> SolutionVersion | None:
    query = select(SolutionVersion).where(
        SolutionVersion.organisation_id == org, SolutionVersion.id == version_id
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


async def published_version_id(session: AsyncSession, org: UUID, schedule_id: UUID) -> UUID | None:
    return await session.scalar(
        select(SolutionVersion.id).where(
            SolutionVersion.organisation_id == org,
            SolutionVersion.schedule_id == schedule_id,
            SolutionVersion.status == "published",
        )
    )


async def mark_published(session: AsyncSession, org: UUID, version_id: UUID, user_id: UUID) -> None:
    await session.execute(
        update(SolutionVersion)
        .where(SolutionVersion.organisation_id == org, SolutionVersion.id == version_id)
        .values(status="published", published_at=func.now(), published_by=user_id)
    )


async def mark_archived(session: AsyncSession, org: UUID, version_id: UUID) -> None:
    await session.execute(
        update(SolutionVersion)
        .where(SolutionVersion.organisation_id == org, SolutionVersion.id == version_id)
        .values(status="archived", archived_at=func.now())
    )


async def placements(
    session: AsyncSession, org: UUID, version_id: UUID
) -> Sequence[tuple[UUID, datetime, str, UUID]]:
    """(activity, start, role, resource) for every resource placed in a version."""
    rows = await session.execute(
        select(
            AssignmentResource.activity_id,
            Assignment.start_at,
            AssignmentResource.role,
            AssignmentResource.resource_id,
        )
        .join(
            Assignment,
            (Assignment.organisation_id == AssignmentResource.organisation_id)
            & (Assignment.version_id == AssignmentResource.version_id)
            & (Assignment.activity_id == AssignmentResource.activity_id),
        )
        .where(
            AssignmentResource.organisation_id == org, AssignmentResource.version_id == version_id
        )
    )
    return [(activity, start, role, resource) for activity, start, role, resource in rows]


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


async def schedule_of(session: AsyncSession, org: UUID, schedule_id: UUID) -> Schedule:
    """The version's schedule, even if since soft-deleted."""
    return await session.scalar(
        select(Schedule).where(Schedule.organisation_id == org, Schedule.id == schedule_id)
    ) or _missing(schedule_id)


def _missing(schedule_id: UUID) -> Schedule:
    raise LookupError(f"schedule {schedule_id} missing for an existing version")


async def resource_names(
    session: AsyncSession, org: UUID, resource_ids: Collection[UUID]
) -> dict[UUID, tuple[str, str]]:
    """(code, name) per resource, including soft-deleted ones."""
    if not resource_ids:
        return {}
    rows = await session.execute(
        select(Resource.id, Resource.code, Resource.name).where(
            Resource.organisation_id == org, Resource.id.in_(resource_ids)
        )
    )
    return {rid: (code, name) for rid, code, name in rows}
