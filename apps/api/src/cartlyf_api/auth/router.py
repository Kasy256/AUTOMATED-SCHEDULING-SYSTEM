from typing import Any

from fastapi import APIRouter, BackgroundTasks, Depends, Request, Response

from cartlyf_api.app_state import email_provider_of, engine_of, settings_of
from cartlyf_api.auth.cookies import set_refresh_cookie
from cartlyf_api.auth.schemas import SignupRequest, TokenRequest, TokenResponse
from cartlyf_api.auth.sessions import IssuedSession
from cartlyf_api.auth.signup import confirm_email, sign_up
from cartlyf_api.email.outbox import deliver
from cartlyf_api.errors import problem_response
from cartlyf_api.rate_limit import rate_limit
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import DbSession

router = APIRouter(prefix="/auth", tags=["auth"])
# Any: FastAPI types OpenAPI response docs as dict[str, Any].
_RATE_LIMITED: dict[int | str, dict[str, Any]] = {429: problem_response("Too many attempts")}


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
