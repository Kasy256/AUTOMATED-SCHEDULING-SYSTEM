from datetime import UTC, datetime, timedelta
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_audit
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.passwords import fingerprint, hash_password
from cartlyf_api.auth.permissions import Role
from cartlyf_api.auth.schemas import SignupRequest
from cartlyf_api.auth.sessions import IssuedSession, issue_session
from cartlyf_api.auth.tokens import CONFIRM_AUDIENCE, TokenInvalid, sign, verify
from cartlyf_api.email import messages
from cartlyf_api.email.outbox import QueuedEmail, enqueue
from cartlyf_api.errors import InvalidLink
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import set_context

CONFIRM_LIFETIME = timedelta(hours=24)


async def sign_up(session: AsyncSession, settings: Settings, request: SignupRequest) -> QueuedEmail:
    """Queue a confirmation email; never reveals whether the address already has an account."""
    # Hash on every path so response time doesn't reveal whether the email exists.
    password_hash = hash_password(request.password.get_secret_value())
    user_id = await auth_repo.user_id_by_email(session, request.email)
    if user_id is None:
        user_id = uuid4()
        await auth_repo.insert_user(
            session,
            user_id=user_id,
            email=request.email,
            name=request.name,
            password_hash=password_hash,
            email_verified=False,
        )
    else:
        await set_context(session, None, user_id)
        user = await auth_repo.get_user(session, user_id)
        assert user is not None
        if user.email_verified:
            return await enqueue(session, user_id, messages.account_exists(settings, user.email))
        # The latest sign-up wins; its new hash fingerprint voids every earlier link.
        user.password_hash = password_hash
        user.name = request.name
    token = sign(
        settings.jwt_secret.get_secret_value(),
        CONFIRM_AUDIENCE,
        {
            "sub": str(user_id),
            "org_name": request.organisation_name,
            "tz": request.timezone,
            "pwfp": fingerprint(password_hash),
        },
        CONFIRM_LIFETIME,
        datetime.now(UTC),
    )
    return await enqueue(session, user_id, messages.confirm_email(settings, request.email, token))


async def confirm_email(session: AsyncSession, settings: Settings, token: str) -> IssuedSession:
    try:
        claims = verify(settings.jwt_secret.get_secret_value(), CONFIRM_AUDIENCE, token)
        user_id = UUID(claims["sub"])
        org_name, timezone, pwfp = str(claims["org_name"]), str(claims["tz"]), str(claims["pwfp"])
    except (TokenInvalid, KeyError, ValueError, TypeError) as exc:
        raise InvalidLink() from exc
    await set_context(session, None, user_id)
    user = await auth_repo.get_user(session, user_id)
    if user is None or user.email_verified or fingerprint(user.password_hash) != pwfp:
        raise InvalidLink()
    user.email_verified = True

    organisation_id, membership_id = uuid4(), uuid4()
    await set_context(session, organisation_id, user_id)
    await orgs_repo.insert_organisation(session, organisation_id, org_name, timezone)
    await orgs_repo.insert_membership(
        session,
        membership_id=membership_id,
        organisation_id=organisation_id,
        user_id=user_id,
        status="active",
    )
    await orgs_repo.insert_roles(session, organisation_id, membership_id, [Role.ORG_ADMIN])
    await record_audit(
        session,
        organisation_id=organisation_id,
        actor_user_id=user_id,
        action="organisation.created",
        target_type="organisation",
        target_id=organisation_id,
    )
    return await issue_session(session, settings, user_id, organisation_id)
