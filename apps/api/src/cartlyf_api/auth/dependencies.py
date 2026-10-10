from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartlyf_api.app_state import settings_of
from cartlyf_api.auth.tokens import AccessClaims, TokenInvalid, read_access_token
from cartlyf_api.errors import Unauthorized
from cartlyf_api.tenancy import DbSession, set_context

bearer = HTTPBearer(auto_error=False)


async def access_claims(
    request: Request,
    session: DbSession,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
) -> AccessClaims:
    """Validate the bearer token and set the request's RLS context from it."""
    if credentials is None:
        raise Unauthorized()
    try:
        claims = read_access_token(settings_of(request), credentials.credentials)
    except TokenInvalid as exc:
        raise Unauthorized() from exc
    await set_context(session, claims.organisation_id, claims.user_id)
    return claims


Claims = Annotated[AccessClaims, Depends(access_claims)]
