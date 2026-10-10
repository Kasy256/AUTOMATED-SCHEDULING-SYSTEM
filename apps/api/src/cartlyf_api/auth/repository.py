from datetime import datetime
from uuid import UUID

from sqlalchemy import func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.auth.models import AppUser, RefreshToken

# The two SECURITY DEFINER lookups: id only, usable before any RLS context exists.
_USER_ID_BY_EMAIL = text("SELECT auth.user_id_by_email(:email)")
_REFRESH_TOKEN_OWNER = text("SELECT auth.refresh_token_user_id(:digest)")


async def user_id_by_email(session: AsyncSession, email: str) -> UUID | None:
    return (await session.execute(_USER_ID_BY_EMAIL, {"email": email})).scalar_one_or_none()


async def refresh_token_owner(session: AsyncSession, digest: bytes) -> UUID | None:
    return (await session.execute(_REFRESH_TOKEN_OWNER, {"digest": digest})).scalar_one_or_none()


async def get_user(
    session: AsyncSession, user_id: UUID, *, for_update: bool = False
) -> AppUser | None:
    query = select(AppUser).where(AppUser.id == user_id, AppUser.deleted_at.is_(None))
    return await session.scalar(query.with_for_update() if for_update else query)


async def is_platform_admin(session: AsyncSession, user_id: UUID) -> bool:
    user = await get_user(session, user_id)
    return user is not None and user.is_platform_admin


async def insert_user(
    session: AsyncSession,
    *,
    user_id: UUID,
    email: str,
    name: str,
    password_hash: str | None,
    email_verified: bool,
) -> None:
    await session.execute(
        insert(AppUser).values(
            id=user_id,
            email=email,
            name=name,
            password_hash=password_hash,
            email_verified=email_verified,
        )
    )


async def insert_refresh_token(
    session: AsyncSession,
    *,
    token_id: UUID,
    user_id: UUID,
    family_id: UUID,
    token_hash: bytes,
    active_organisation_id: UUID | None,
    expires_at: datetime,
) -> None:
    await session.execute(
        insert(RefreshToken).values(
            id=token_id,
            user_id=user_id,
            family_id=family_id,
            token_hash=token_hash,
            active_organisation_id=active_organisation_id,
            expires_at=expires_at,
        )
    )


async def get_refresh_token_for_update(session: AsyncSession, digest: bytes) -> RefreshToken | None:
    return await session.scalar(
        select(RefreshToken).where(RefreshToken.token_hash == digest).with_for_update()
    )


async def revoke_family(session: AsyncSession, family_id: UUID) -> None:
    await session.execute(
        update(RefreshToken)
        .where(RefreshToken.family_id == family_id, RefreshToken.revoked_at.is_(None))
        .values(revoked_at=func.now())
    )
