from uuid import UUID, uuid4

import httpx2 as httpx
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from support import Account, execute_many, fetch, seed_org, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def _join(pg: PostgresContainer, account: Account, organisation_id: UUID, role: str) -> None:
    user_id = fetch(superuser_url(pg), f"SELECT id FROM app_user WHERE email = '{account.email}'")
    membership_id = uuid4()
    execute_many(
        superuser_url(pg),
        [
            "INSERT INTO membership (id, organisation_id, user_id, status) "
            f"VALUES ('{membership_id}', '{organisation_id}', '{user_id[0][0]}', 'active')",
            "INSERT INTO membership_role (organisation_id, membership_id, role) "
            f"VALUES ('{organisation_id}', '{membership_id}', '{role}')",
        ],
    )


def _switch(
    client: TestClient, bearer: Account, cookie_owner: Account, organisation_id: UUID
) -> httpx.Response:
    client.cookies.clear()
    return client.post(
        "/api/v1/auth/switch-organisation",
        headers={**bearer.auth, "Cookie": f"{REFRESH_COOKIE}={cookie_owner.refresh_token}"},
        json={"organisation_id": str(organisation_id)},
    )


def test_switch_to_another_membership(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app, org_name="Alpha")
    other = seed_org(superuser_url(migrated_pg), "Beta")
    _join(migrated_pg, account, other.organisation_id, "planner")

    me = client.get("/api/v1/auth/me", headers=account.auth).json()
    assert {o["name"] for o in me["organisations"]} == {"Alpha", "Beta"}
    assert me["roles"] == ["org_admin"]

    switched = _switch(client, account, account, other.organisation_id)
    assert switched.status_code == 200
    assert switched.json()["organisation_id"] == str(other.organisation_id)
    assert REFRESH_COOKIE in switched.cookies
    token = switched.json()["access_token"]
    me = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"}).json()
    assert me["organisation_id"] == str(other.organisation_id)
    assert me["roles"] == ["planner"]


def test_switch_to_non_member_org_is_404(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    stranger = seed_org(superuser_url(migrated_pg), "Stranger")
    response = _switch(client, account, account, stranger.organisation_id)
    assert response.status_code == 404


def test_switch_with_someone_elses_cookie_is_401(client: TestClient, app: FastAPI) -> None:
    mine = signup_and_confirm(client, app)
    theirs = signup_and_confirm(client, app)
    response = _switch(client, mine, theirs, theirs.organisation_id)
    assert response.status_code == 401


def test_switch_requires_bearer(client: TestClient, app: FastAPI) -> None:
    account = signup_and_confirm(client, app)
    client.cookies.clear()
    response = client.post(
        "/api/v1/auth/switch-organisation",
        headers={"Cookie": f"{REFRESH_COOKIE}={account.refresh_token}"},
        json={"organisation_id": str(account.organisation_id)},
    )
    assert response.status_code == 401
