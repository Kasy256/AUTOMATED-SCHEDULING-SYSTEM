from datetime import UTC, datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from cartlyf_api.auth.tokens import issue_access_token, read_access_token
from support import fetch, refresh_with, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def _bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}


def test_AUTH_03_refresh_rotates(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    response = refresh_with(client, account.refresh_token)
    assert response.status_code == 200
    new_raw = response.cookies[REFRESH_COOKIE]
    assert new_raw != account.refresh_token
    body = response.json()
    assert body["organisation_id"] == str(account.organisation_id)
    assert client.get("/api/v1/auth/me", headers=_bearer(body["access_token"])).status_code == 200
    assert refresh_with(client, new_raw).status_code == 200


def test_AUTH_03_reuse_revokes_family(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    rotated = refresh_with(client, account.refresh_token).cookies[REFRESH_COOKIE]
    replay = refresh_with(client, account.refresh_token)
    assert replay.status_code == 401
    # The legitimate rotated token dies too: the revocation was committed despite the 401.
    assert refresh_with(client, rotated).status_code == 401
    live = fetch(
        superuser_url(migrated_pg),
        "SELECT count(*) FROM refresh_token t JOIN app_user u ON u.id = t.user_id "
        f"WHERE u.email = '{account.email}' AND t.revoked_at IS NULL",
    )
    assert live == [(0,)]


def test_AUTH_03_missing_or_garbage_cookie_is_401(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/v1/auth/refresh").status_code == 401
    assert refresh_with(client, "garbage").status_code == 401


def test_AUTH_03_expired_refresh_token_is_401(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    fetch(
        superuser_url(migrated_pg),
        "UPDATE refresh_token t SET expires_at = now() - interval '1 second' FROM app_user u "
        f"WHERE u.id = t.user_id AND u.email = '{account.email}' RETURNING t.id",
    )
    assert refresh_with(client, account.refresh_token).status_code == 401


def test_AUTH_03_logout_revokes(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    response = client.post(
        "/api/v1/auth/logout", headers={"Cookie": f"{REFRESH_COOKIE}={account.refresh_token}"}
    )
    assert response.status_code == 204
    assert refresh_with(client, account.refresh_token).status_code == 401


def test_logout_without_cookie_is_204(client: TestClient) -> None:
    client.cookies.clear()
    assert client.post("/api/v1/auth/logout").status_code == 204


def test_AUTH_03_expired_access_token_rejected_by_api(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    settings = app.state.settings
    claims = read_access_token(settings, account.access_token)
    stale = issue_access_token(settings, claims, datetime.now(UTC) - timedelta(minutes=16))
    response = client.get("/api/v1/auth/me", headers=_bearer(stale))
    assert response.status_code == 401
    assert response.headers["www-authenticate"] == "Bearer"


def test_me_requires_a_token(client: TestClient) -> None:
    assert client.get("/api/v1/auth/me").status_code == 401


def test_me_describes_the_session(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app, org_name="Me Org")
    body = client.get("/api/v1/auth/me", headers=account.auth).json()
    assert body["email"] == account.email
    assert body["organisation_id"] == str(account.organisation_id)
    assert body["roles"] == ["org_admin"]
    assert body["platform_admin_session"] is False
    assert body["organisations"] == [
        {"organisation_id": str(account.organisation_id), "name": "Me Org"}
    ]
