from datetime import UTC, datetime
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_audit
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.schemas import TokenResponse
from cartlyf_api.auth.tokens import AccessClaims, issue_access_token
from cartlyf_api.errors import NotFound
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import set_context


async def start_platform_session(
    session: AsyncSession, settings: Settings, claims: AccessClaims, organisation_id: UUID
) -> TokenResponse:
    """Issue a short, audited access token that lets a platform admin act inside one org."""
    # 404 for everyone else too: the platform path should not reveal itself.
    if claims.platform_admin or not await auth_repo.is_platform_admin(session, claims.user_id):
        raise NotFound()
    await set_context(session, organisation_id, claims.user_id)
    if await orgs_repo.get_organisation(session, organisation_id) is None:
        raise NotFound()
    await record_audit(
        session,
        organisation_id=organisation_id,
        actor_user_id=claims.user_id,
        action="platform_admin.session_started",
        target_type="organisation",
        target_id=organisation_id,
        via_platform_admin=True,
    )
    token = issue_access_token(
        settings, AccessClaims(claims.user_id, organisation_id, True), datetime.now(UTC)
    )
    return TokenResponse(
        access_token=token,
        expires_in=settings.access_token_minutes * 60,
        organisation_id=organisation_id,
    )
