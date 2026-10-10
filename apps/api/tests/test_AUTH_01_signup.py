import asyncio

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from cartlyf_api.auth.signup import confirm_email
from cartlyf_api.errors import InvalidLink
from cartlyf_api.tenancy import scoped_transaction
from support import (
    APP,
    DEFAULT_PASSWORD,
    db_url,
    fetch,
    latest_link_token,
    sent_emails,
    signup,
    signup_and_confirm,
    signup_body,
    superuser_url,
)

pytestmark = pytest.mark.integration


def test_AUTH_01_signup_confirm_creates_org_with_admin(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    email = signup(client, org_name="Kampala Clinic", timezone="Africa/Kampala")
    token = latest_link_token(app, email, "confirm-email")
    response = client.post("/api/v1/auth/confirm-email", json={"token": token})
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 900
    assert REFRESH_COOKIE in response.cookies

    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT o.name, o.timezone, r.role, u.email_verified "
        "FROM app_user u JOIN membership m ON m.user_id = u.id "
        "JOIN organisation o ON o.id = m.organisation_id "
        "JOIN membership_role r ON r.membership_id = m.id "
        f"WHERE u.email = '{email}'",
    )
    assert rows == [("Kampala Clinic", "Africa/Kampala", "org_admin", True)]
    audit = fetch(
        superuser_url(migrated_pg),
        f"SELECT action FROM audit_log WHERE organisation_id = '{body['organisation_id']}'",
    )
    assert audit == [("organisation.created",)]


def test_AUTH_01_no_org_before_confirmation(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    email = signup(client)
    assert sent_emails(app).sent[-1].to == email
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT u.email_verified, count(m.id) FROM app_user u "
        f"LEFT JOIN membership m ON m.user_id = u.id WHERE u.email = '{email}' "
        "GROUP BY u.email_verified",
    )
    assert rows == [(False, 0)]


def test_AUTH_01_confirm_link_is_single_use(client: TestClient, app: FastAPI) -> None:
    email = signup(client)
    token = latest_link_token(app, email, "confirm-email")
    assert client.post("/api/v1/auth/confirm-email", json={"token": token}).status_code == 200
    second = client.post("/api/v1/auth/confirm-email", json={"token": token})
    assert second.status_code == 400
    assert second.json()["title"] == "Invalid or expired link"


def test_AUTH_01_garbage_confirm_token_is_400(client: TestClient) -> None:
    response = client.post("/api/v1/auth/confirm-email", json={"token": "not-a-jwt"})
    assert response.status_code == 400


def test_AUTH_01_later_signup_invalidates_earlier_link(client: TestClient, app: FastAPI) -> None:
    email = signup(client)
    first = latest_link_token(app, email, "confirm-email")
    signup(client, email=email, password="another long password")
    assert client.post("/api/v1/auth/confirm-email", json={"token": first}).status_code == 400
    latest = latest_link_token(app, email, "confirm-email")
    assert client.post("/api/v1/auth/confirm-email", json={"token": latest}).status_code == 200


def test_AUTH_01_signup_existing_verified_email_is_indistinguishable(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    query = f"SELECT password_hash FROM app_user WHERE email = '{account.email}'"
    before = fetch(superuser_url(migrated_pg), query)
    response = client.post("/api/v1/auth/signup", json=signup_body(account.email, "x" * 16))
    assert response.status_code == 202
    assert response.content == b""
    assert fetch(superuser_url(migrated_pg), query) == before
    last = sent_emails(app).sent[-1]
    assert last.to == account.email
    assert "already have an account" in last.body


def test_signup_email_is_case_insensitive(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    signup(client, email=account.email.upper())
    assert "already have an account" in sent_emails(app).sent[-1].body


def test_signup_rejects_unknown_timezone(client: TestClient) -> None:
    body = signup_body("tz@example.com", DEFAULT_PASSWORD, timezone="Mars/Olympus")
    assert client.post("/api/v1/auth/signup", json=body).status_code == 422


def test_signup_rejects_short_password_without_echoing_it(client: TestClient) -> None:
    body = signup_body("short@example.com", "pw-tiny")
    response = client.post("/api/v1/auth/signup", json=body)
    assert response.status_code == 422
    assert "pw-tiny" not in response.text


def test_AUTH_01_concurrent_confirms_create_one_org(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    email = signup(client)
    token = latest_link_token(app, email, "confirm-email")

    async def confirm_once(engine: AsyncEngine) -> str:
        try:
            async with scoped_transaction(engine) as session:
                await confirm_email(session, app.state.settings, token)
        except InvalidLink:
            return "invalid"
        return "ok"

    async def run() -> list[str]:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            return list(await asyncio.gather(confirm_once(engine), confirm_once(engine)))
        finally:
            await engine.dispose()

    assert sorted(asyncio.run(run())) == ["invalid", "ok"]
    orgs = fetch(
        superuser_url(migrated_pg),
        "SELECT count(*) FROM membership m JOIN app_user u ON u.id = m.user_id "
        f"WHERE u.email = '{email}'",
    )
    assert orgs == [(1,)]
