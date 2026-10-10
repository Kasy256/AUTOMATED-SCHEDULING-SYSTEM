from datetime import UTC, datetime, timedelta
from uuid import uuid4

import jwt
import pytest

from cartlyf_api.auth.tokens import (
    ACCESS_AUDIENCE,
    CONFIRM_AUDIENCE,
    AccessClaims,
    TokenInvalid,
    hash_refresh_token,
    issue_access_token,
    new_refresh_token,
    read_access_token,
    sign,
    verify,
)
from support import TEST_JWT_SECRET, make_settings

SETTINGS = make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0")


def test_AUTH_03_access_token_lives_15_minutes() -> None:
    token = issue_access_token(SETTINGS, AccessClaims(uuid4(), uuid4()), datetime.now(UTC))
    payload = jwt.decode(token, options={"verify_signature": False})  # pyright: ignore[reportUnknownMemberType]
    assert payload["exp"] - payload["iat"] == 15 * 60


def test_AUTH_03_expired_access_token_rejected() -> None:
    claims = AccessClaims(uuid4(), uuid4())
    old = issue_access_token(SETTINGS, claims, datetime.now(UTC) - timedelta(minutes=16))
    with pytest.raises(TokenInvalid):
        read_access_token(SETTINGS, old)


def test_access_token_round_trip() -> None:
    claims = AccessClaims(uuid4(), None, platform_admin=True)
    token = issue_access_token(SETTINGS, claims, datetime.now(UTC))
    assert read_access_token(SETTINGS, token) == claims


def test_audience_confusion_rejected() -> None:
    link = sign(
        TEST_JWT_SECRET,
        CONFIRM_AUDIENCE,
        {"sub": str(uuid4())},
        timedelta(hours=1),
        datetime.now(UTC),
    )
    with pytest.raises(TokenInvalid):
        verify(TEST_JWT_SECRET, ACCESS_AUDIENCE, link)


def test_wrong_secret_rejected() -> None:
    token = issue_access_token(SETTINGS, AccessClaims(uuid4(), uuid4()), datetime.now(UTC))
    other = make_settings("postgresql+asyncpg://u:p@h/db", "redis://h:1/0", jwt_secret="y" * 40)
    with pytest.raises(TokenInvalid):
        read_access_token(other, token)


def test_unsigned_token_rejected() -> None:
    forged = jwt.encode(  # pyright: ignore[reportUnknownMemberType]
        {"sub": str(uuid4()), "aud": ACCESS_AUDIENCE, "iat": 0, "exp": 4102444800},
        key="",
        algorithm="none",
    )
    with pytest.raises(TokenInvalid):
        read_access_token(SETTINGS, forged)


def test_refresh_token_hash_is_stable_and_secret_is_random() -> None:
    raw, digest = new_refresh_token()
    assert hash_refresh_token(raw) == digest
    assert new_refresh_token()[0] != raw
