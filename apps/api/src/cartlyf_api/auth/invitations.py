from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.audit.service import record_audit
from cartlyf_api.auth import repository as auth_repo
from cartlyf_api.auth.passwords import hash_password, verify_password
from cartlyf_api.auth.schemas import AcceptInvitationRequest
from cartlyf_api.auth.sessions import IssuedSession, issue_session
from cartlyf_api.auth.tokens import INVITE_AUDIENCE, TokenInvalid, verify
from cartlyf_api.errors import InvalidLink, Unauthorized
from cartlyf_api.orgs import repository as orgs_repo
from cartlyf_api.settings import Settings
from cartlyf_api.tenancy import set_context


async def accept_invitation(
    session: AsyncSession, settings: Settings, request: AcceptInvitationRequest
) -> IssuedSession:
    """Activate a pending membership: new people set a password, existing users prove theirs."""
    try:
        claims = verify(settings.jwt_secret.get_secret_value(), INVITE_AUDIENCE, request.token)
        user_id, org_id = UUID(claims["sub"]), UUID(claims["org"])
        membership_id = UUID(claims["mid"])
    except (TokenInvalid, KeyError, ValueError, TypeError) as exc:
        raise InvalidLink() from exc
    await set_context(session, org_id, user_id)
    membership = await orgs_repo.get_membership(session, org_id, membership_id)
    user = await auth_repo.get_user(session, user_id)
    if (
        membership is None
        or user is None
        or membership.user_id != user_id
        or membership.status != "invited"
    ):
        raise InvalidLink()
    password = request.password.get_secret_value()
    if user.password_hash is None:
        user.password_hash = hash_password(password)
        user.email_verified = True  # the link proves they control the address
    elif not verify_password(user.password_hash, password):
        raise Unauthorized("Invalid email or password")
    membership.status = "active"
    await record_audit(
        session,
        organisation_id=org_id,
        actor_user_id=user_id,
        action="invitation.accepted",
        target_type="membership",
        target_id=membership_id,
    )
    return await issue_session(session, settings, user_id, org_id)
