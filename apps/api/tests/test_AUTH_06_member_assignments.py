import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    add_member,
    build_schedule,
    execute,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration


def _publish(pg: PostgresContainer, version_id: str) -> None:
    # Owner SQL until the publish endpoint exists.
    execute(
        superuser_url(pg),
        f"UPDATE solution_version SET status = 'published', published_at = now() "
        f"WHERE id = '{version_id}'",
    )


def _link(client: TestClient, admin_auth: dict[str, str], resource_id: str, user_id: str) -> None:
    response = client.patch(
        f"/api/v1/resources/{resource_id}", headers=admin_auth, json={"user_id": user_id}
    )
    assert response.status_code == 200, response.text


def test_AUTH_06_member_sees_only_published_and_own_assignments(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin, lecturers=2, demands=4, sessions=1)
    _, version = solve_now(client, admin, built.schedule_id)
    me = client.get("/api/v1/auth/me", headers=member.auth).json()["user_id"]
    url = f"/api/v1/solution-versions/{version}"
    full = client.get(url, headers=admin.auth).json()["assignments"]
    mine = full[0]["resources"]["lecturer"][0]
    _link(client, admin.auth, mine, me)

    assert client.get(url, headers=member.auth).status_code == 404
    assert client.get("/api/v1/me/assignments", headers=member.auth).json() == []

    _publish(migrated_pg, version)
    expected = [a for a in full if mine in a["resources"]["lecturer"]]
    assert expected

    response = client.get(url, headers=member.auth)
    assert response.status_code == 200, response.text
    assignments = response.json()["assignments"]
    assert {a["activity_id"] for a in assignments} == {a["activity_id"] for a in expected}
    assert all(mine in a["resources"]["lecturer"] for a in assignments)

    own = client.get("/api/v1/me/assignments", headers=member.auth)
    assert own.status_code == 200, own.text
    rows = own.json()
    assert {r["activity_id"] for r in rows} == {a["activity_id"] for a in expected}
    assert all(r["version_id"] == version and r["roles"] == ["lecturer"] for r in rows)
    assert [r["start_at"] for r in rows] == sorted(r["start_at"] for r in rows)


def test_AUTH_06_unlinked_member_gets_empty_published_version(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    _publish(migrated_pg, version)
    response = client.get(f"/api/v1/solution-versions/{version}", headers=member.auth)
    assert response.status_code == 200
    assert response.json()["assignments"] == []


def test_AUTH_06_member_cannot_list_schedule_versions(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    member = add_member(client, app, admin, ["member"])
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    listing = client.get(f"/api/v1/schedules/{built.schedule_id}/versions", headers=member.auth)
    assert listing.status_code == 403
    diff = client.get(f"/api/v1/solution-versions/{version}/diff/{version}", headers=member.auth)
    assert diff.status_code == 403


def test_AUTH_06_member_in_other_org_gets_404(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    other_admin = signup_and_confirm(client, app)
    outsider = add_member(client, app, other_admin, ["member"])
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    _publish(migrated_pg, version)
    response = client.get(f"/api/v1/solution-versions/{version}", headers=outsider.auth)
    assert response.status_code == 404
