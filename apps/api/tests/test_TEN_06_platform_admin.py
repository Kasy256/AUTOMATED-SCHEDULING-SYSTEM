from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from support import Account, execute, fetch, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


def _make_platform_admin(pg: PostgresContainer, email: str, value: bool = True) -> None:
    execute(
        superuser_url(pg),
        f"UPDATE app_user SET is_platform_admin = {str(value).lower()} WHERE email = '{email}'",
    )


def _enter(client: TestClient, admin: Account, organisation_id: UUID) -> dict[str, str]:
    started = client.post(
        f"/api/v1/platform/organisations/{organisation_id}/session", headers=admin.auth
    )
    assert started.status_code == 200, started.text
    return {"Authorization": f"Bearer {started.json()['access_token']}"}


def test_TEN_06_platform_admin_enters_org_and_every_use_is_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app, org_name="Ops")
    target = signup_and_confirm(client, app, org_name="Customer")
    _make_platform_admin(migrated_pg, admin.email)

    started = client.post(
        f"/api/v1/platform/organisations/{target.organisation_id}/session", headers=admin.auth
    )
    assert started.status_code == 200
    assert started.json()["organisation_id"] == str(target.organisation_id)
    assert started.json()["expires_in"] == 900
    assert REFRESH_COOKIE not in started.cookies
    pa = {"Authorization": f"Bearer {started.json()['access_token']}"}

    listed = client.get("/api/v1/members", headers=pa)
    assert listed.status_code == 200
    assert {m["email"] for m in listed.json()} == {target.email}
    me = client.get("/api/v1/auth/me", headers=pa).json()
    assert me["platform_admin_session"] is True

    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT action, via_platform_admin, details->>'path' FROM audit_log "
        f"WHERE organisation_id = '{target.organisation_id}' AND via_platform_admin "
        "ORDER BY id",
    )
    assert rows == [
        ("platform_admin.session_started", True, None),
        ("platform_admin.request", True, "/api/v1/members"),
        ("platform_admin.request", True, "/api/v1/auth/me"),
    ]


def test_TEN_06_mutation_via_platform_admin_is_marked_in_audit(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    target = signup_and_confirm(client, app)
    _make_platform_admin(migrated_pg, admin.email)
    pa = _enter(client, admin, target.organisation_id)
    invited = client.post(
        "/api/v1/invitations",
        headers=pa,
        json={"email": f"{uuid4().hex}@example.com", "name": "Via PA", "roles": ["viewer"]},
    )
    assert invited.status_code == 201
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT via_platform_admin FROM audit_log "
        f"WHERE organisation_id = '{target.organisation_id}' AND action = 'member.invited'",
    )
    assert rows == [(True,)]


def test_TEN_06_non_admin_gets_404(client: TestClient, app: FastAPI) -> None:
    user = signup_and_confirm(client, app)
    other = signup_and_confirm(client, app)
    response = client.post(
        f"/api/v1/platform/organisations/{other.organisation_id}/session", headers=user.auth
    )
    assert response.status_code == 404


def test_TEN_06_unknown_org_is_404(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    _make_platform_admin(migrated_pg, admin.email)
    response = client.post(f"/api/v1/platform/organisations/{uuid4()}/session", headers=admin.auth)
    assert response.status_code == 404


def test_TEN_06_platform_session_is_bound_to_one_org(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    target = signup_and_confirm(client, app)
    third = signup_and_confirm(client, app)
    _make_platform_admin(migrated_pg, admin.email)
    pa = _enter(client, admin, target.organisation_id)
    emails = {m["email"] for m in client.get("/api/v1/members", headers=pa).json()}
    assert third.email not in emails
    nested = client.post(
        f"/api/v1/platform/organisations/{third.organisation_id}/session", headers=pa
    )
    assert nested.status_code == 404


def test_TEN_06_revoked_admin_token_stops_working(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    target = signup_and_confirm(client, app)
    _make_platform_admin(migrated_pg, admin.email)
    pa = _enter(client, admin, target.organisation_id)
    _make_platform_admin(migrated_pg, admin.email, value=False)
    assert client.get("/api/v1/members", headers=pa).status_code == 401


def test_TEN_06_failed_request_still_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    target = signup_and_confirm(client, app)
    _make_platform_admin(migrated_pg, admin.email)
    pa = _enter(client, admin, target.organisation_id)
    missing = uuid4()
    assert client.get(f"/api/v1/members/{missing}", headers=pa).status_code == 404
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT count(*) FROM audit_log WHERE action = 'platform_admin.request' "
        f"AND details->>'path' = '/api/v1/members/{missing}'",
    )
    assert rows == [(1,)]
