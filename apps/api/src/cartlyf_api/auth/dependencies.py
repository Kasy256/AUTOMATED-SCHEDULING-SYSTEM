from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from cartlyf_api.app_state import engine_of, settings_of
from cartlyf_api.audit.service import record_audit
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.permissions import Principal, Role
from cartlyf_api.auth.tokens import AccessClaims, TokenInvalid, read_access_token
from cartlyf_api.errors import Forbidden, Unauthorized
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.tenancy import DbSession, scoped_transaction, set_context

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
    if claims.platform_admin:
        await _audit_platform_admin_use(request, session, claims)
    return claims


async def _audit_platform_admin_use(
    request: Request, session: DbSession, claims: AccessClaims
) -> None:
    if claims.organisation_id is None or not await auth_repo.is_platform_admin(
        session, claims.user_id
    ):
        raise Unauthorized()
    # Own transaction: the audit row must survive even if the request itself fails.
    async with scoped_transaction(
        engine_of(request), claims.organisation_id, claims.user_id
    ) as audit:
        await record_audit(
            audit,
            organisation_id=claims.organisation_id,
            actor_user_id=claims.user_id,
            action="platform_admin.request",
            details={"method": request.method, "path": request.url.path},
            via_platform_admin=True,
        )


Claims = Annotated[AccessClaims, Depends(access_claims)]


async def current_principal(session: DbSession, claims: Claims) -> Principal:
    if claims.organisation_id is None:
        raise Forbidden("No organisation selected")
    if claims.platform_admin:
        # Already verified and audited in access_claims; acts as an org admin of that org only.
        roles = frozenset({Role.ORG_ADMIN})
        return Principal(claims.user_id, claims.organisation_id, roles, via_platform_admin=True)
    roles = await orgs_repo.active_roles(session, claims.organisation_id, claims.user_id)
    if roles is None:
        raise Unauthorized()
    return Principal(claims.user_id, claims.organisation_id, roles)


CurrentPrincipal = Annotated[Principal, Depends(current_principal)]
