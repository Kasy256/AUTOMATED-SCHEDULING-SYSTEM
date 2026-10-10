import time
from typing import Annotated, Any

from fastapi import APIRouter, BackgroundTasks, Cookie, Depends, Request, Response
from fastapi.responses import JSONResponse

from cartlyf_api.app_state import email_provider_of, engine_of, redis_of, settings_of
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.cookies import REFRESH_COOKIE, clear_refresh_cookie, set_refresh_cookie
from cartlyf_api.auth.dependencies import Claims
from cartlyf_api.auth.permissions import Role
from cartlyf_api.auth.schemas import (
    LoginRequest,
    MeResponse,
    OrganisationSummary,
    SignupRequest,
    TokenRequest,
    TokenResponse,
)
from cartlyf_api.auth.sessions import IssuedSession, RefreshRejected, login, logout, rotate
from cartlyf_api.auth.signup import confirm_email, sign_up
from cartlyf_api.email.outbox import deliver
from cartlyf_api.errors import Unauthorized, problem, problem_response
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.rate_limit import WINDOW_SECONDS, enforce, rate_limit
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_RATE_LIMITED: dict[int | str, dict[str, Any]] = {429: problem_response("Too many attempts")}
_UNAUTHORIZED: dict[int | str, dict[str, Any]] = {401: problem_response("Not authenticated")}
RefreshCookie = Annotated[str | None, Cookie(alias=REFRESH_COOKIE)]


def _token_response(response: Response, settings: Settings, issued: IssuedSession) -> TokenResponse:
    set_refresh_cookie(response, settings, issued.refresh_token)
    return TokenResponse(
        access_token=issued.access_token,
        expires_in=issued.expires_in,
        organisation_id=issued.organisation_id,
    )


@router.post(
    "/signup",
    status_code=202,
    response_class=Response,
    dependencies=[Depends(rate_limit("signup"))],
    responses=_RATE_LIMITED,
)
async def signup(
    request: Request, body: SignupRequest, session: DbSession, background: BackgroundTasks
) -> Response:
    queued = await sign_up(session, settings_of(request), body)
    # Background tasks run after the response, so after the request transaction commits.
    background.add_task(deliver, engine_of(request), email_provider_of(request), queued)
    return Response(status_code=202)


@router.post(
    "/confirm-email",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("confirm"))],
    responses={400: problem_response("Invalid or expired link"), **_RATE_LIMITED},
)
async def confirm_email_route(
    request: Request, body: TokenRequest, session: DbSession, response: Response
) -> TokenResponse:
    settings = settings_of(request)
    issued = await confirm_email(session, settings, body.token)
    return _token_response(response, settings, issued)


def _rejected(settings: Settings) -> JSONResponse:
    response = problem(401, "Unauthorized", headers={"WWW-Authenticate": "Bearer"})
    clear_refresh_cookie(response, settings)
    return response


@router.post(
    "/login",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("login"))],
    responses={
        401: problem_response("Invalid email or password"),
        403: problem_response("Email address not confirmed"),
        **_RATE_LIMITED,
    },
)
async def login_route(
    request: Request, body: LoginRequest, session: DbSession, response: Response
) -> TokenResponse:
    settings = settings_of(request)
    await enforce(
        redis_of(request),
        f"login:email:{body.email.lower()}",
        settings.auth_rate_limit_per_minute,
        WINDOW_SECONDS,
        time.time(),
    )
    return _token_response(response, settings, await login(session, settings, body))


@router.post(
    "/refresh",
    response_model=TokenResponse,
    dependencies=[Depends(rate_limit("refresh"))],
    responses={**_UNAUTHORIZED, **_RATE_LIMITED},
)
async def refresh_route(
    request: Request, session: DbSession, response: Response, refresh_cookie: RefreshCookie = None
) -> TokenResponse | JSONResponse:
    settings = settings_of(request)
    result = await rotate(session, settings, refresh_cookie)
    if isinstance(result, RefreshRejected):
        # Returned, not raised: raising would roll back the family revocation.
        return _rejected(settings)
    return _token_response(response, settings, result)


@router.post("/logout", status_code=204, response_class=Response)
async def logout_route(
    request: Request, session: DbSession, refresh_cookie: RefreshCookie = None
) -> Response:
    await logout(session, refresh_cookie)
    response = Response(status_code=204)
    clear_refresh_cookie(response, settings_of(request))
    return response


@router.get("/me", response_model=MeResponse, responses=_UNAUTHORIZED)
async def me(session: DbSession, claims: Claims) -> MeResponse:
    user = await auth_repo.get_user(session, claims.user_id)
    if user is None:
        raise Unauthorized()
    roles: frozenset[Role] = frozenset()
    if claims.platform_admin:
        roles = frozenset({Role.ORG_ADMIN})
    elif claims.organisation_id is not None:
        roles = await orgs_repo.active_roles(session, claims.organisation_id, user.id) or roles
    organisations = await orgs_repo.membership_summaries(session, user.id)
    return MeResponse(
        user_id=user.id,
        email=user.email,
        name=user.name,
        organisation_id=claims.organisation_id,
        roles=sorted(roles),
        platform_admin_session=claims.platform_admin,
        organisations=[OrganisationSummary(organisation_id=i, name=n) for i, n in organisations],
    )
