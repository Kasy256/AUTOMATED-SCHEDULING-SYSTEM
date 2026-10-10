from uuid import uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import add_member, fetch, latest_link_token, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration
NEW_PASSWORD = "a brand new password"


def test_AUTH_05_invite_accept_set_password(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    email = f"{uuid4().hex}@example.com"
    invited = client.post(
        "/api/v1/invitations",
        headers=admin.auth,
        json={"email": email, "name": "New Person", "roles": ["planner"]},
    )
    assert invited.status_code == 201
    membership_id = invited.json()["membership_id"]
    state = (
        "SELECT u.password_hash IS NOT NULL, u.email_verified, m.status FROM app_user u "
        f"JOIN membership m ON m.user_id = u.id WHERE m.id = '{membership_id}'"
    )
    assert fetch(superuser_url(migrated_pg), state) == [(False, False, "invited")]
    assert (
        client.post(
            "/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD}
        ).status_code
        == 401
    )

    token = latest_link_token(app, email, "accept-invitation")
    accepted = client.post(
        "/api/v1/auth/accept-invitation", json={"token": token, "password": NEW_PASSWORD}
    )
    assert accepted.status_code == 200
    assert accepted.json()["organisation_id"] == str(admin.organisation_id)
    assert fetch(superuser_url(migrated_pg), state) == [(True, True, "active")]
    login = client.post("/api/v1/auth/login", json={"email": email, "password": NEW_PASSWORD})
    assert login.status_code == 200

    reuse = client.post(
        "/api/v1/auth/accept-invitation", json={"token": token, "password": NEW_PASSWORD}
    )
    assert reuse.status_code == 400


def test_AUTH_05_existing_user_accepts_with_own_password(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app, org_name="Inviter")
    other = signup_and_confirm(client, app, org_name="Elsewhere")
    invited = client.post(
        "/api/v1/invitations",
        headers=admin.auth,
        json={"email": other.email, "name": "ignored", "roles": ["viewer"]},
    )
    assert invited.status_code == 201
    token = latest_link_token(app, other.email, "accept-invitation")
    wrong = client.post(
        "/api/v1/auth/accept-invitation",
        json={"token": token, "password": "definitely not theirs"},
    )
    assert wrong.status_code == 401
    right = client.post(
        "/api/v1/auth/accept-invitation", json={"token": token, "password": other.password}
    )
    assert right.status_code == 200
    assert right.json()["organisation_id"] == str(admin.organisation_id)


def test_tampered_invitation_token_is_400(client: TestClient) -> None:
    response = client.post(
        "/api/v1/auth/accept-invitation", json={"token": "x.y.z", "password": NEW_PASSWORD}
    )
    assert response.status_code == 400


def test_invite_existing_active_member_conflicts(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    response = client.post(
        "/api/v1/invitations",
        headers=admin.auth,
        json={"email": admin.email, "name": "me", "roles": ["viewer"]},
    )
    assert response.status_code == 409


def test_reinvite_pending_member_resends_and_updates_roles(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    email = f"{uuid4().hex}@example.com"
    body = {"email": email, "name": "Pending", "roles": ["viewer"]}
    first = client.post("/api/v1/invitations", headers=admin.auth, json=body)
    again = client.post(
        "/api/v1/invitations", headers=admin.auth, json={**body, "roles": ["planner"]}
    )
    assert again.status_code == 201
    assert again.json()["membership_id"] == first.json()["membership_id"]
    member = client.get(
        f"/api/v1/members/{first.json()['membership_id']}", headers=admin.auth
    ).json()
    assert member["roles"] == ["planner"]
    assert member["status"] == "invited"


def test_invitation_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    add_member(client, app, admin, ["viewer"])
    actions = fetch(
        superuser_url(migrated_pg),
        f"SELECT action FROM audit_log WHERE organisation_id = '{admin.organisation_id}' "
        "ORDER BY id",
    )
    assert actions == [("organisation.created",), ("member.invited",), ("invitation.accepted",)]
