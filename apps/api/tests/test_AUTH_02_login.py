from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from cartlyf_api.main import create_app
from support import (
    APP,
    DEFAULT_PASSWORD,
    db_url,
    fetch,
    make_settings,
    signup,
    signup_and_confirm,
    superuser_url,
)

pytestmark = pytest.mark.integration
WRONG = {"password": "not the password"}


def test_AUTH_02_password_stored_as_argon2id(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    rows = fetch(
        superuser_url(migrated_pg),
        f"SELECT password_hash FROM app_user WHERE email = '{account.email}'",
    )
    assert rows[0][0].startswith("$argon2id$")


def test_AUTH_02_login_succeeds_case_insensitively(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    response = client.post(
        "/api/v1/auth/login",
        json={"email": account.email.upper(), "password": account.password},
    )
    assert response.status_code == 200
    assert response.json()["organisation_id"] == str(account.organisation_id)
    assert REFRESH_COOKIE in response.cookies


def test_AUTH_02_wrong_password_and_unknown_email_identical(
    client: TestClient, app: FastAPI
) -> None:
    account = signup_and_confirm(client, app)
    wrong = client.post("/api/v1/auth/login", json={"email": account.email, **WRONG})
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", **WRONG})
    assert wrong.status_code == unknown.status_code == 401
    assert wrong.json() == unknown.json()
    assert wrong.headers.get("www-authenticate") == unknown.headers.get("www-authenticate")
    assert REFRESH_COOKIE not in wrong.cookies
    assert REFRESH_COOKIE not in unknown.cookies


def test_AUTH_02_invited_user_without_password_gets_same_401(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    unknown = client.post("/api/v1/auth/login", json={"email": "nobody@example.com", **WRONG})
    superuser = superuser_url(migrated_pg)
    fetch(
        superuser,
        f"UPDATE app_user SET password_hash = NULL WHERE email = '{account.email}' RETURNING id",
    )
    no_password = client.post("/api/v1/auth/login", json={"email": account.email, **WRONG})
    assert no_password.status_code == 401
    assert no_password.json() == unknown.json()


def test_unverified_account_cannot_log_in(client: TestClient) -> None:
    email = signup(client)
    response = client.post(
        "/api/v1/auth/login", json={"email": email, "password": DEFAULT_PASSWORD}
    )
    assert response.status_code == 403
    assert response.json()["detail"] == "Email address not confirmed"


def test_AUTH_02_login_rate_limited_per_ip(client: TestClient) -> None:
    statuses = [
        client.post("/api/v1/auth/login", json={"email": f"n{i}@example.com", **WRONG}).status_code
        for i in range(11)
    ]
    assert statuses[:10] == [401] * 10
    assert statuses[10] == 429


@pytest.fixture
def strict_app(migrated_pg: PostgresContainer, redis_url: str) -> FastAPI:
    settings = make_settings(db_url(migrated_pg, *APP), redis_url, auth_rate_limit_per_minute=3)
    return create_app(settings)


@pytest.fixture
def second_ip(strict_app: FastAPI) -> Iterator[TestClient]:
    with TestClient(strict_app, client=("10.0.0.2", 50000)) as client:
        yield client


def test_AUTH_02_login_rate_limited_per_email(strict_app: FastAPI, second_ip: TestClient) -> None:
    victim = {"email": "victim@example.com", **WRONG}
    with TestClient(strict_app) as first_ip:
        assert [first_ip.post("/api/v1/auth/login", json=victim).status_code for _ in range(3)] == [
            401
        ] * 3
    blocked = second_ip.post("/api/v1/auth/login", json=victim)
    assert blocked.status_code == 429
    assert int(blocked.headers["retry-after"]) > 0
    other = second_ip.post("/api/v1/auth/login", json={"email": "other@example.com", **WRONG})
    assert other.status_code == 401
