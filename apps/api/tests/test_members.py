from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import add_member, fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def _membership_id(client: TestClient, admin_auth: dict[str, str], email: str) -> str:
    members = client.get("/api/v1/members", headers=admin_auth).json()
    return next(m["membership_id"] for m in members if m["email"] == email)


def test_last_org_admin_cannot_be_removed(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    membership_id = _membership_id(client, admin.auth, admin.email)
    response = client.put(
        f"/api/v1/members/{membership_id}/roles", headers=admin.auth, json={"roles": ["planner"]}
    )
    assert response.status_code == 409


def test_admin_can_step_down_when_another_admin_exists(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    add_member(client, app, admin, ["org_admin"])
    membership_id = _membership_id(client, admin.auth, admin.email)
    response = client.put(
        f"/api/v1/members/{membership_id}/roles", headers=admin.auth, json={"roles": ["planner"]}
    )
    assert response.status_code == 200


def test_role_change_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    viewer = add_member(client, app, admin, ["viewer"])
    membership_id = _membership_id(client, admin.auth, viewer.email)
    client.put(
        f"/api/v1/members/{membership_id}/roles",
        headers=admin.auth,
        json={"roles": ["planner", "member"]},
    )
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT details->'from', details->'to', target_id::text FROM audit_log "
        f"WHERE action = 'member.roles_changed' AND organisation_id = '{admin.organisation_id}'",
    )
    assert rows == [(["viewer"], ["member", "planner"], membership_id)]


def test_member_list_only_shows_own_org(client: TestClient, app: FastAPI) -> None:
    a = signup_and_confirm(client, app, org_name="A")
    b = signup_and_confirm(client, app, org_name="B")
    emails = {m["email"] for m in client.get("/api/v1/members", headers=a.auth).json()}
    assert emails == {a.email}
    assert b.email not in emails


def test_unknown_member_is_404(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    assert client.get(f"/api/v1/members/{uuid4()}", headers=admin.auth).status_code == 404


def test_roles_must_be_non_empty(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    membership_id = _membership_id(client, admin.auth, admin.email)
    response = client.put(
        f"/api/v1/members/{membership_id}/roles", headers=admin.auth, json={"roles": []}
    )
    assert response.status_code == 422
