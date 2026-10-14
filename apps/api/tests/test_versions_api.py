import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    add_member,
    build_schedule,
    execute,
    seed_config,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration


def test_list_and_get_versions(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2)
    _, first = solve_now(client, admin, built.schedule_id)
    _, second = solve_now(client, admin, built.schedule_id)

    listed = client.get(f"/api/v1/schedules/{built.schedule_id}/versions", headers=admin.auth)
    assert listed.status_code == 200, listed.text
    rows = listed.json()
    assert [r["number"] for r in rows] == [2, 1]
    assert all(r["hard_violations"] == 0 and r["status"] == "draft" for r in rows)

    detail = client.get(f"/api/v1/solution-versions/{first}", headers=admin.auth)
    assert detail.status_code == 200, detail.text
    body = detail.json()
    assert body["number"] == 1 and body["id"] == first
    assert body["score"]["hard_violations"] == 0
    assert len(body["assignments"]) == built.activities
    assert all(a["activity_name"] and a["resources"]["lecturer"] for a in body["assignments"])
    assert second != first


def test_diff_endpoint(client: TestClient, app: FastAPI, migrated_pg: PostgresContainer) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2)
    _, first = solve_now(client, admin, built.schedule_id)
    _, second = solve_now(client, admin, built.schedule_id)
    execute(
        superuser_url(migrated_pg),
        f"UPDATE assignment SET start_at = start_at + interval '7 days' "
        f"WHERE version_id = '{second}' AND activity_id = "
        f"(SELECT activity_id FROM assignment WHERE version_id = '{second}' LIMIT 1)",
    )
    response = client.get(f"/api/v1/solution-versions/{first}/diff/{second}", headers=admin.auth)
    assert response.status_code == 200, response.text
    body = response.json()
    assert len(body["moved"]) >= 1
    moved = body["moved"][0]
    assert moved["before"]["start_at"] != moved["after"]["start_at"]
    assert body["added"] == [] and body["removed"] == []


def test_diff_across_schedules_is_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    v1 = seed_config(client, admin)["version_id"]
    built = build_schedule(client, admin)
    _, v2 = solve_now(client, admin, built.schedule_id)
    response = client.get(f"/api/v1/solution-versions/{v1}/diff/{v2}", headers=admin.auth)
    assert response.status_code == 422
    assert response.json()["errors"][0]["loc"] == ["path", "other_version_id"]


def test_versions_are_not_visible_across_orgs(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    other = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    assert client.get(f"/api/v1/solution-versions/{version}", headers=other.auth).status_code == 404
    listing = client.get(f"/api/v1/schedules/{built.schedule_id}/versions", headers=other.auth)
    assert listing.status_code == 404


def test_viewer_reads_versions(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    viewer = add_member(client, app, admin, ["viewer"])
    built = build_schedule(client, admin)
    _, version = solve_now(client, admin, built.schedule_id)
    assert (
        client.get(f"/api/v1/solution-versions/{version}", headers=viewer.auth).status_code == 200
    )
