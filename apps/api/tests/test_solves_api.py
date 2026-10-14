from uuid import uuid4

import pytest
import redis
import redis.exceptions
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    add_member,
    execute,
    fetch,
    redis_queue_length,
    seed_config,
    signup_and_confirm,
    superuser_url,
)

pytestmark = pytest.mark.integration


def _solves(schedule_id: str) -> str:
    return f"/api/v1/schedules/{schedule_id}/solves"


def test_request_solve_returns_202_and_queues_message(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    before = redis_queue_length(app, "solves")
    r = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={})
    assert r.status_code == 202, r.text
    assert r.json()["status"] == "queued"
    assert redis_queue_length(app, "solves") == before + 1
    run = client.get(f"/api/v1/solves/{r.json()['id']}", headers=admin.auth).json()
    feasibility = client.get(
        f"/api/v1/schedules/{ids['schedule_id']}/feasibility", headers=admin.auth
    ).json()
    assert run["problem_hash"] == feasibility["problem_hash"]


def test_time_limit_above_max_is_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    r = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={"time_limit_s": 601})
    assert r.status_code == 422
    assert r.json()["errors"][0]["loc"] == ["body", "time_limit_s"]


def test_JOB_06_org_cap_returns_429(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    url = _solves(ids["schedule_id"])
    first = client.post(url, headers=admin.auth, json={})
    second = client.post(url, headers=admin.auth, json={})
    assert (first.status_code, second.status_code) == (202, 202)
    third = client.post(url, headers=admin.auth, json={})
    assert third.status_code == 429
    assert "Retry-After" in third.headers
    cancel = client.post(f"/api/v1/solves/{first.json()['id']}/cancel", headers=admin.auth)
    assert cancel.status_code == 202
    assert client.post(url, headers=admin.auth, json={}).status_code == 202


def test_cancel_queued_run_is_cancelled_immediately(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    run = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={}).json()
    r = client.post(f"/api/v1/solves/{run['id']}/cancel", headers=admin.auth)
    assert r.status_code == 202
    assert r.json()["status"] == "cancelled"
    assert r.json()["finished_at"] is not None
    again = client.post(f"/api/v1/solves/{run['id']}/cancel", headers=admin.auth)
    assert again.status_code == 409


def test_enqueue_failure_marks_run_failed_and_returns_503(
    client: TestClient, app: FastAPI, monkeypatch: pytest.MonkeyPatch
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)

    def boom(*_: object, **__: object) -> None:
        raise redis.exceptions.ConnectionError("down")

    monkeypatch.setattr(app.state.broker, "enqueue", boom)
    r = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={})
    assert r.status_code == 503
    assert "down" not in r.text
    runs = client.get(_solves(ids["schedule_id"]), headers=admin.auth).json()
    failed = [run for run in runs if run["status"] == "failed"]
    assert [run["error"] for run in failed] == ["Could not queue the solve"]


def test_viewer_reads_runs_member_cannot(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    viewer = add_member(client, app, admin, ["viewer"])
    member = add_member(client, app, admin, ["member"])
    run_id = ids["run_id"]
    assert client.get(_solves(ids["schedule_id"]), headers=viewer.auth).status_code == 200
    assert client.get(f"/api/v1/solves/{run_id}", headers=viewer.auth).status_code == 200
    assert client.get(_solves(ids["schedule_id"]), headers=member.auth).status_code == 403
    assert client.get(f"/api/v1/solves/{run_id}", headers=member.auth).status_code == 403
    assert client.post(_solves(ids["schedule_id"]), headers=viewer.auth, json={}).status_code == 403
    cancel = client.post(f"/api/v1/solves/{run_id}/cancel", headers=viewer.auth)
    assert cancel.status_code == 403


def test_solve_request_is_audited(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    run = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={}).json()
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT action, target_type FROM audit_log "
        f"WHERE target_id = '{run['id']}' AND organisation_id = '{admin.organisation_id}'",
    )
    assert rows == [("solve.requested", "solve_run")]


def test_unsupported_template_still_queues(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    r = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={"seed": 7})
    assert r.status_code == 202


def test_stale_runs_are_failed_on_read(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    url = _solves(ids["schedule_id"])
    queued = client.post(url, headers=admin.auth, json={}).json()["id"]
    running = client.post(url, headers=admin.auth, json={}).json()["id"]
    db = superuser_url(migrated_pg)
    execute(
        db,
        f"UPDATE solve_run SET created_at = now() - interval '2 hours' WHERE id = '{queued}'",
    )
    execute(
        db,
        "UPDATE solve_run SET status = 'running', started_at = now(), "
        f"heartbeat_at = now() - interval '5 minutes' WHERE id = '{running}'",
    )
    got = client.get(f"/api/v1/solves/{queued}", headers=admin.auth).json()
    assert (got["status"], got["error"]) == ("failed", "never started")
    got = client.get(f"/api/v1/solves/{running}", headers=admin.auth).json()
    assert (got["status"], got["error"]) == ("failed", "worker stopped responding")
    rows = fetch(db, f"SELECT status FROM solve_run WHERE id = '{queued}'")
    assert rows == [("failed",)]


def test_seed_above_int32_is_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    ids = seed_config(client, admin)
    r = client.post(_solves(ids["schedule_id"]), headers=admin.auth, json={"seed": 2**31})
    assert r.status_code == 422
    assert r.json()["errors"][0]["loc"] == ["body", "seed"]


def test_unknown_schedule_is_404_before_time_limit_422(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    r = client.post(_solves(str(uuid4())), headers=admin.auth, json={"time_limit_s": 601})
    assert r.status_code == 404
