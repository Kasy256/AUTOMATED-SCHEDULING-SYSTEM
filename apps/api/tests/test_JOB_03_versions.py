from datetime import datetime

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.exc import DBAPIError, ProgrammingError
from testcontainers.community.postgres import PostgresContainer

from support import (
    APP,
    KAMPALA,
    build_schedule,
    db_url,
    execute_many,
    fetch,
    free_start,
    get_version,
    move,
    publish,
    signup_and_confirm,
    solve_now,
    superuser_url,
)

pytestmark = pytest.mark.integration


def test_JOB_03_published_version_rejects_updates(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version_id = solve_now(client, admin, built.schedule_id)
    response = publish(client, admin, version_id)
    assert response.status_code == 200, response.text
    assert response.json()["status"] == "published"
    assert response.json()["published_at"] is not None

    org = str(admin.organisation_id)
    app_url = db_url(migrated_pg, *APP)
    context = f"SELECT set_config('app.current_org', '{org}', true)"
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(
            app_url,
            [context, f"UPDATE assignment SET end_at = now() WHERE version_id = '{version_id}'"],
        )
    with pytest.raises(DBAPIError, match="invalid version transition"):
        execute_many(
            app_url,
            [context, f"UPDATE solution_version SET status = 'draft' WHERE id = '{version_id}'"],
        )

    again = publish(client, admin, version_id)
    assert again.status_code == 409, again.text
    url = f"/api/v1/solution-versions/{version_id}"
    archived = client.post(f"{url}/archive", headers=admin.auth)
    assert archived.status_code == 200, archived.text
    assert archived.json()["status"] == "archived"
    assert archived.json()["archived_at"] is not None
    assert client.post(f"{url}/archive", headers=admin.auth).status_code == 409
    assert publish(client, admin, version_id).status_code == 409
    for method in ("PUT", "PATCH", "DELETE"):
        response = client.request(method, url, headers=admin.auth, json={})
        assert response.status_code == 405, f"{method} -> {response.status_code}"


def test_JOB_03_editing_creates_new_draft(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2, sessions=1)
    _, version_id = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, version_id).status_code == 200
    before = get_version(client, admin, version_id)
    target = before["assignments"][0]
    to = free_start(before["assignments"])

    response = move(client, admin, version_id, target, to)
    assert response.status_code == 201, response.text
    draft = response.json()
    assert draft["status"] == "draft"
    assert draft["number"] == before["number"] + 1
    assert draft["parent_version_id"] == version_id
    assert draft["solver_status"] == "EDITED"
    assert draft["solve_run_id"] == before["solve_run_id"]
    assert draft["hard_violations"] == 0
    moved = next(a for a in draft["assignments"] if a["activity_id"] == target["activity_id"])
    assert datetime.fromisoformat(moved["start_at"]) == to
    assert moved["resources"] == target["resources"]
    others = [a for a in draft["assignments"] if a["activity_id"] != target["activity_id"]]
    assert others == [a for a in before["assignments"] if a["activity_id"] != target["activity_id"]]
    assert get_version(client, admin, version_id) == before

    # A draft can be edited again, into yet another draft.
    again = move(client, admin, draft["id"], moved, free_start(draft["assignments"]))
    assert again.status_code == 201, again.text
    assert again.json()["parent_version_id"] == draft["id"]


def test_draft_with_hard_violation_is_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2, sessions=1)
    _, version_id = solve_now(client, admin, built.schedule_id)
    first, second = get_version(client, admin, version_id)["assignments"]
    occupied = datetime.fromisoformat(second["start_at"])

    response = move(client, admin, version_id, first, occupied)
    assert response.status_code == 422, response.text
    body = response.json()
    assert body["detail"] == "The edit breaks hard rules"
    assert any("core:overlap" in e["msg"] for e in body["errors"])
    assert all(e["loc"] == ["body", "changes"] for e in body["errors"])
    listed = client.get(f"/api/v1/schedules/{built.schedule_id}/versions", headers=admin.auth)
    assert len(listed.json()) == 1


def test_draft_start_not_a_candidate_is_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version_id = solve_now(client, admin, built.schedule_id)
    target = get_version(client, admin, version_id)["assignments"][0]
    off_grid = datetime(2027, 1, 11, 8, 30, tzinfo=KAMPALA)

    response = move(client, admin, version_id, target, off_grid)
    assert response.status_code == 422, response.text
    assert response.json()["errors"][0]["loc"] == ["body", "changes", 0, "start_at"]


def test_draft_rejects_bad_requests(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, version_id = solve_now(client, admin, built.schedule_id)
    target = get_version(client, admin, version_id)["assignments"][0]
    url = f"/api/v1/solution-versions/{version_id}/drafts"
    change = {
        "activity_id": target["activity_id"],
        "start_at": target["start_at"],
        "resources": target["resources"],
    }

    duplicate = client.post(url, headers=admin.auth, json={"changes": [change, change]})
    assert duplicate.status_code == 422, duplicate.text
    twice = {**change, "resources": {r: ids + ids for r, ids in target["resources"].items()}}
    repeated = client.post(url, headers=admin.auth, json={"changes": [twice]})
    assert repeated.status_code == 201, repeated.text
    naive = {**change, "start_at": "2027-01-11T08:00:00"}
    assert client.post(url, headers=admin.auth, json={"changes": [naive]}).status_code == 422
    assert client.post(url, headers=admin.auth, json={"changes": []}).status_code == 422
    unknown = {**change, "activity_id": "00000000-0000-4000-8000-0000000000ff"}
    assert client.post(url, headers=admin.auth, json={"changes": [unknown]}).status_code == 404
    stranger = {**change, "resources": {"lecturer": ["00000000-0000-4000-8000-0000000000ff"]}}
    assert client.post(url, headers=admin.auth, json={"changes": [stranger]}).status_code == 404


def test_publish_archives_previous_published(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    _, first = solve_now(client, admin, built.schedule_id)
    _, second = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, first).status_code == 200
    assert publish(client, admin, second).status_code == 200

    old = get_version(client, admin, first)
    assert old["status"] == "archived" and old["archived_at"] is not None
    assert get_version(client, admin, second)["status"] == "published"
    listed = client.get(f"/api/v1/schedules/{built.schedule_id}/versions", headers=admin.auth)
    assert [v["status"] for v in listed.json()].count("published") == 1


def test_publish_is_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, demands=2, sessions=1)
    _, first = solve_now(client, admin, built.schedule_id)
    assert publish(client, admin, first).status_code == 200
    assignments = get_version(client, admin, first)["assignments"]
    draft = move(client, admin, first, assignments[0], free_start(assignments)).json()["id"]
    assert publish(client, admin, draft).status_code == 200
    archived = client.post(f"/api/v1/solution-versions/{draft}/archive", headers=admin.auth)
    assert archived.status_code == 200, archived.text

    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT action, target_id::text, details FROM audit_log "
        f"WHERE organisation_id = '{admin.organisation_id}' AND action LIKE 'version.%' "
        "ORDER BY id",
    )
    actions = [(action, target) for action, target, _ in rows]
    assert actions == [
        ("version.published", first),
        ("version.draft_created", draft),
        ("version.published", draft),
        ("version.archived", draft),
    ]
    second_publish = rows[2][2]
    assert second_publish["previous_version_id"] == first
    assert second_publish["recipients"] == 0
    assert rows[0][2]["previous_version_id"] is None
