from collections.abc import Sequence
from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.feeds.models import CalendarFeed
from cartlyf_api.schedules.models import Schedule
from cartlyf_api.versions.models import Assignment, AssignmentResource, SolutionVersion


async def insert_feed(
    session: AsyncSession, org: UUID, resource_id: UUID, token_hash: bytes, user_id: UUID
) -> CalendarFeed:
    row = await session.scalar(
        insert(CalendarFeed)
        .values(
            id=uuid4(),
            organisation_id=org,
            resource_id=resource_id,
            token_hash=token_hash,
            created_by=user_id,
        )
        .returning(CalendarFeed)
    )
    assert row is not None
    return row


async def get_feed(
    session: AsyncSession, org: UUID, feed_id: UUID, *, for_update: bool = False
) -> CalendarFeed | None:
    query = select(CalendarFeed).where(
        CalendarFeed.organisation_id == org, CalendarFeed.id == feed_id
    )
    if for_update:
        query = query.with_for_update().execution_options(populate_existing=True)
    return await session.scalar(query)


async def list_feeds(session: AsyncSession, org: UUID, resource_id: UUID) -> Sequence[CalendarFeed]:
    rows = await session.scalars(
        select(CalendarFeed)
        .where(CalendarFeed.organisation_id == org, CalendarFeed.resource_id == resource_id)
        .order_by(CalendarFeed.created_at, CalendarFeed.id)
    )
    return rows.all()


async def revoke(session: AsyncSession, org: UUID, feed_id: UUID) -> None:
    await session.execute(
        update(CalendarFeed)
        .where(CalendarFeed.organisation_id == org, CalendarFeed.id == feed_id)
        .values(revoked_at=func.now())
    )


async def org_for_token(session: AsyncSession, token_hash: bytes) -> UUID | None:
    """The org of a live feed; a definer function, since no tenant context exists yet."""
    return await session.scalar(text("SELECT auth.calendar_feed_org(:h)"), {"h": token_hash})


async def live_feed(session: AsyncSession, org: UUID, token_hash: bytes) -> CalendarFeed | None:
    return await session.scalar(
        select(CalendarFeed).where(
            CalendarFeed.organisation_id == org,
            CalendarFeed.token_hash == token_hash,
            CalendarFeed.revoked_at.is_(None),
        )
    )


async def published_assignments(
    session: AsyncSession, org: UUID, resource_id: UUID
) -> Sequence[tuple[UUID, datetime, datetime, datetime]]:
    """(activity, start, end, published_at) of the resource in every published version."""
    rows = await session.execute(
        select(
            Assignment.activity_id,
            Assignment.start_at,
            Assignment.end_at,
            SolutionVersion.published_at,
        )
        .join(
            AssignmentResource,
            (AssignmentResource.organisation_id == Assignment.organisation_id)
            & (AssignmentResource.version_id == Assignment.version_id)
            & (AssignmentResource.activity_id == Assignment.activity_id),
        )
        .join(
            SolutionVersion,
            (SolutionVersion.organisation_id == Assignment.organisation_id)
            & (SolutionVersion.id == Assignment.version_id),
        )
        .join(
            Schedule,
            (Schedule.organisation_id == SolutionVersion.organisation_id)
            & (Schedule.id == SolutionVersion.schedule_id),
        )
        .where(
            Assignment.organisation_id == org,
            AssignmentResource.resource_id == resource_id,
            SolutionVersion.status == "published",
            Schedule.deleted_at.is_(None),
        )
        .distinct()
        .order_by(Assignment.start_at, Assignment.activity_id)
    )
    return [
        (activity, start, end, published_at)
        for activity, start, end, published_at in rows
        if published_at is not None
    ]
