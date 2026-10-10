from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartlyf_api.app_state import settings_of
from cartlyf_api.auth.permissions import Principal
from cartlyf_api.auth.tokens import AccessClaims, TokenInvalid, read_access_token
from cartlyf_api.errors import Forbidden, Unauthorized
from cartlyf_api.orgs import repository as orgs_repo
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


async def current_principal(session: DbSession, claims: Claims) -> Principal:
    if claims.organisation_id is None:
        raise Forbidden("No organisation selected")
    if claims.platform_admin:
        # The audited platform-admin path is added with the platform module.
        raise Unauthorized()
    roles = await orgs_repo.active_roles(session, claims.organisation_id, claims.user_id)
    if roles is None:
        raise Unauthorized()
    return Principal(claims.user_id, claims.organisation_id, roles)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
