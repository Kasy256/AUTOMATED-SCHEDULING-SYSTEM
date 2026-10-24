import hashlib
import secrets
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from cartlyf_api.audit.service import record_change
from cartlyf_api.auth.permissions import Permission, Principal, Role
from cartlyf_api.errors import Forbidden, NotFound
from cartlyf_api.feeds import repository
from cartlyf_api.feeds.ical import Event, calendar
from cartlyf_api.feeds.models import CalendarFeed
from cartlyf_api.feeds.schemas import FeedCreated, FeedOut
from cartlyf_api.resources import repository as resources_repo
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_api.versions import repository as versions_repo


def _hash(token: str) -> bytes:
    return hashlib.sha256(token.encode()).digest()


def _out(feed: CalendarFeed) -> FeedOut:
    return FeedOut(
        id=feed.id,
        resource_id=feed.resource_id,
        created_at=feed.created_at,
        revoked_at=feed.revoked_at,
    )


def _require_self_service(principal: Principal) -> None:
    """Members manage their own feeds; config managers may use the same routes for theirs."""
    if Role.MEMBER not in principal.roles:
        principal.require(Permission.CONFIG_MANAGE)


async def _require_resource(session: AsyncSession, org: UUID, resource_id: UUID) -> None:
    if await resources_repo.get_resource(session, org, resource_id) is None:
        raise NotFound("Unknown resource")


async def _own_resource(session: AsyncSession, principal: Principal) -> UUID:
    # At most one: a unique index allows one live resource per user per org.
    own = await resources_repo.resource_ids_for_user(
        session, principal.organisation_id, principal.user_id
    )
    if not own:
        raise NotFound("No resource is linked to you")
    return own[0]


async def _create(
    session: AsyncSession, settings: Settings, principal: Principal, resource_id: UUID
) -> FeedCreated:
    token = secrets.token_urlsafe(32)
    feed = await repository.insert_feed(
        session, principal.organisation_id, resource_id, _hash(token), principal.user_id
    )
    await record_change(
        session,
        principal,
        "calendar_feed.created",
        "calendar_feed",
        feed.id,
        {"resource_id": str(resource_id)},
    )
    base = str(settings.public_api_base_url).rstrip("/")
    return FeedCreated(
        id=feed.id,
        resource_id=resource_id,
        url=f"{base}/api/v1/calendar/{token}.ics",
        created_at=feed.created_at,
    )


async def create_feed(
    session: AsyncSession, settings: Settings, principal: Principal, resource_id: UUID
) -> FeedCreated:
    principal.require(Permission.CONFIG_MANAGE)
    await _require_resource(session, principal.organisation_id, resource_id)
    return await _create(session, settings, principal, resource_id)


async def create_own_feed(
    session: AsyncSession, settings: Settings, principal: Principal
) -> FeedCreated:
    _require_self_service(principal)
    return await _create(session, settings, principal, await _own_resource(session, principal))


async def list_feeds(
    session: AsyncSession, principal: Principal, resource_id: UUID
) -> list[FeedOut]:
    principal.require(Permission.CONFIG_MANAGE)
    org = principal.organisation_id
    await _require_resource(session, org, resource_id)
    return [_out(feed) for feed in await repository.list_feeds(session, org, resource_id)]


async def list_own_feeds(session: AsyncSession, principal: Principal) -> list[FeedOut]:
    _require_self_service(principal)
    resource_id = await _own_resource(session, principal)
    feeds = await repository.list_feeds(session, principal.organisation_id, resource_id)
    return [_out(feed) for feed in feeds]


async def revoke_feed(session: AsyncSession, principal: Principal, feed_id: UUID) -> None:
    """Idempotent: revoking a revoked feed changes nothing and is not audited again."""
    manager = principal.has(Permission.CONFIG_MANAGE)
    if not manager and Role.MEMBER not in principal.roles:
        raise Forbidden()
    org = principal.organisation_id
    feed = await repository.get_feed(session, org, feed_id, for_update=True)
    if feed is None:
        raise NotFound("Unknown calendar feed")
    if not manager:
        own = await resources_repo.resource_ids_for_user(session, org, principal.user_id)
        if feed.resource_id not in own:
            raise NotFound("Unknown calendar feed")
    if feed.revoked_at is not None:
        return
    await repository.revoke(session, org, feed_id)
    await record_change(session, principal, "calendar_feed.revoked", "calendar_feed", feed_id)


async def feed_body(engine: AsyncEngine, token: str) -> str:
    """The iCal text of a live feed; unknown and revoked tokens are indistinguishable."""
    token_hash = _hash(token)
    async with scoped_transaction(engine) as session:
        org = await repository.org_for_token(session, token_hash)
    if org is None:
        raise NotFound()
    async with scoped_transaction(engine, org) as session:
        feed = await repository.live_feed(session, org, token_hash)
        if feed is None:
            raise NotFound()
        resource = await resources_repo.get_resource(session, org, feed.resource_id)
        if resource is None:
            raise NotFound()
        rows = await repository.published_assignments(session, org, resource.id)
        names = await versions_repo.activity_names(session, org, {row[0] for row in rows})
    events = [
        Event(
            uid=f"{activity_id}@cartlyf",
            start=start,
            end=end,
            summary=names.get(activity_id) or str(activity_id),
            stamp=published_at,
        )
        for activity_id, start, end, published_at in rows
    ]
    return calendar(resource.name, events)
