from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.tokens import AccessClaims, issue_access_token, new_refresh_token
from cartlyf_api.settings import Settings


@dataclass(frozen=True)
class IssuedSession:
    access_token: str
    refresh_token: str
    organisation_id: UUID | None
    expires_in: int


async def issue_session(
    session: AsyncSession,
    settings: Settings,
    user_id: UUID,
    organisation_id: UUID | None,
    family_id: UUID | None = None,
) -> IssuedSession:
    """New access token plus a refresh token in `family_id` (a new family when None).

    The RLS context must already name `user_id`.
    """
    now = datetime.now(UTC)
    raw, digest = new_refresh_token()
    await auth_repo.insert_refresh_token(
        session,
        token_id=uuid4(),
        user_id=user_id,
        family_id=family_id or uuid4(),
        token_hash=digest,
        active_organisation_id=organisation_id,
        expires_at=now + timedelta(days=settings.refresh_token_days),
    )
    access = issue_access_token(settings, AccessClaims(user_id, organisation_id), now)
    return IssuedSession(access, raw, organisation_id, settings.access_token_minutes * 60)
