from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, Request, Response

from cartlyf_api.app_state import engine_of, settings_of
from cartlyf_api.auth.dependencies import CurrentPrincipal
from cartlyf_api.errors import problem_response
from cartlyf_api.feeds import service
from cartlyf_api.feeds.schemas import FeedCreated, FeedOut
from cartlyf_api.rate_limit import rate_limit
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import DbSession

router = APIRouter(tags=["calendar-feeds"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_ONE: dict[int | str, dict[str, Any]] = {
    401: problem_response("Not authenticated"),
    403: problem_response("Missing permission"),
    404: problem_response("Not found"),
}


def _feed_limit(settings: Settings) -> int:
    return settings.feed_rate_limit_per_minute


@router.post(
    "/resources/{resource_id}/calendar-feeds",
    status_code=201,
    response_model=FeedCreated,
    responses=_ONE,
)
async def create_calendar_feed(
    request: Request, resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> FeedCreated:
    return await service.create_feed(session, settings_of(request), principal, resource_id)


@router.get("/resources/{resource_id}/calendar-feeds", response_model=list[FeedOut], responses=_ONE)
async def list_calendar_feeds(
    resource_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> list[FeedOut]:
    return await service.list_feeds(session, principal, resource_id)


@router.post("/me/calendar-feeds", status_code=201, response_model=FeedCreated, responses=_ONE)
async def create_my_calendar_feed(
    request: Request, session: DbSession, principal: CurrentPrincipal
) -> FeedCreated:
    return await service.create_own_feed(session, settings_of(request), principal)


@router.get("/me/calendar-feeds", response_model=list[FeedOut], responses=_ONE)
async def list_my_calendar_feeds(session: DbSession, principal: CurrentPrincipal) -> list[FeedOut]:
    return await service.list_own_feeds(session, principal)


@router.delete("/calendar-feeds/{calendar_feed_id}", status_code=204, responses=_ONE)
async def revoke_calendar_feed(
    calendar_feed_id: UUID, session: DbSession, principal: CurrentPrincipal
) -> Response:
    await service.revoke_feed(session, principal, calendar_feed_id)
    return Response(status_code=204)


# No bearer auth: calendar apps cannot send one, so the unguessable token is the credential.
@router.get(
    "/calendar/{token}.ics",
    response_class=Response,
    responses={
        200: {"content": {"text/calendar": {}}, "description": "The feed in iCalendar format"},
        404: problem_response("Unknown or revoked feed"),
        429: problem_response("Too many requests"),
    },
    dependencies=[Depends(rate_limit("feeds", _feed_limit))],
)
async def calendar_feed(request: Request, token: str) -> Response:
    body = await service.feed_body(engine_of(request), token)
    return Response(
        body,
        media_type="text/calendar; charset=utf-8",
        headers={"Cache-Control": "private, max-age=300"},
    )
