from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.passwords import hash_password, needs_rehash, verify_password
from cartlyf_api.auth.schemas import LoginRequest
from cartlyf_api.auth.tokens import (
    AccessClaims,
    hash_refresh_token,
    issue_access_token,
    new_refresh_token,
)
from cartlyf_api.errors import Forbidden, NotFound, Unauthorized
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import set_context

log = structlog.get_logger()


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


class RefreshRejected:
    """Refresh refused after a state change (family revoked) that must still commit."""


async def login(session: AsyncSession, settings: Settings, request: LoginRequest) -> IssuedSession:
    user_id = await auth_repo.user_id_by_email(session, request.email)
    user = None
    if user_id is not None:
        await set_context(session, None, user_id)
        user = await auth_repo.get_user(session, user_id)
    password = request.password.get_secret_value()
    # verify_password runs even when the user is unknown, so both paths take the same time.
    if not verify_password(user.password_hash if user else None, password) or user is None:
        raise Unauthorized("Invalid email or password")
    if not user.email_verified:
        raise Forbidden("Email address not confirmed")
    if user.password_hash and needs_rehash(user.password_hash):
        user.password_hash = hash_password(password)
    organisation_id = await orgs_repo.default_organisation(session, user.id)
    return await issue_session(session, settings, user.id, organisation_id)


async def rotate(
    session: AsyncSession,
    settings: Settings,
    raw: str | None,
    expected_user_id: UUID | None = None,
    switch_to: UUID | None = None,
) -> IssuedSession | RefreshRejected:
    """Exchange a refresh token for a new pair; reusing a spent token revokes its family."""
    if not raw:
        raise Unauthorized()
    digest = hash_refresh_token(raw)
    user_id = await auth_repo.refresh_token_owner(session, digest)
    if user_id is None or (expected_user_id is not None and user_id != expected_user_id):
        raise Unauthorized()
    await set_context(session, None, user_id)
    token = await auth_repo.get_refresh_token_for_update(session, digest)
    if token is None:
        raise Unauthorized()
    if token.used_at is not None or token.revoked_at is not None:
        await auth_repo.revoke_family(session, token.family_id)
        log.warning("refresh_token_reuse", user_id=str(user_id), family_id=str(token.family_id))
        return RefreshRejected()
    now = datetime.now(UTC)
    if token.expires_at <= now:
        raise Unauthorized()
    token.used_at = now
    organisation_id = switch_to if switch_to is not None else token.active_organisation_id
    if organisation_id is not None and not await orgs_repo.is_active_member(
        session, organisation_id, user_id
    ):
        if switch_to is not None:
            raise NotFound()
        organisation_id = None
    return await issue_session(session, settings, user_id, organisation_id, token.family_id)


async def logout(session: AsyncSession, raw: str | None) -> None:
    if not raw:
        return
    digest = hash_refresh_token(raw)
    user_id = await auth_repo.refresh_token_owner(session, digest)
    if user_id is None:
        return
    await set_context(session, None, user_id)
    token = await auth_repo.get_refresh_token_for_update(session, digest)
    if token is not None:
        await auth_repo.revoke_family(session, token.family_id)
