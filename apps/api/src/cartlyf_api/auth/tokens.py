import hashlib
import secrets
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from cartlyf_api.settings import Settings

ACCESS_AUDIENCE = "cartlyf:access"
CONFIRM_AUDIENCE = "cartlyf:confirm-email"
INVITE_AUDIENCE = "cartlyf:invitation"
_ALGORITHM = "HS256"


class TokenInvalid(Exception):
    pass


@dataclass(frozen=True)
class AccessClaims:
    user_id: UUID
    organisation_id: UUID | None
    platform_admin: bool = False


def sign(
    secret: str, audience: str, claims: Mapping[str, object], lifetime: timedelta, now: datetime
) -> str:
    payload = {**claims, "aud": audience, "iat": now, "exp": now + lifetime}
    # PyJWT's stubs leave header/encoder kwargs untyped.
    return jwt.encode(payload, secret, algorithm=_ALGORITHM)  # pyright: ignore[reportUnknownMemberType]


# Any: decoded JWT payloads are untyped JSON; callers convert each claim explicitly.
def verify(secret: str, audience: str, token: str) -> dict[str, Any]:
    try:
        return jwt.decode(  # pyright: ignore[reportUnknownMemberType]
            token,
            secret,
            algorithms=[_ALGORITHM],
            audience=audience,
            options={"require": ["exp", "iat", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        raise TokenInvalid from exc


def issue_access_token(settings: Settings, claims: AccessClaims, now: datetime) -> str:
    org = None if claims.organisation_id is None else str(claims.organisation_id)
    return sign(
        settings.jwt_secret.get_secret_value(),
        ACCESS_AUDIENCE,
        {"sub": str(claims.user_id), "org": org, "pa": claims.platform_admin},
        timedelta(minutes=settings.access_token_minutes),
        now,
    )


def read_access_token(settings: Settings, token: str) -> AccessClaims:
    data = verify(settings.jwt_secret.get_secret_value(), ACCESS_AUDIENCE, token)
    try:
        org = data.get("org")
        return AccessClaims(
            UUID(data["sub"]), None if org is None else UUID(org), data.get("pa") is True
        )
    except (KeyError, ValueError, TypeError, AttributeError) as exc:
        raise TokenInvalid from exc


def new_refresh_token() -> tuple[str, bytes]:
    raw = secrets.token_urlsafe(32)
    return raw, hash_refresh_token(raw)


def hash_refresh_token(raw: str) -> bytes:
    return hashlib.sha256(raw.encode()).digest()
