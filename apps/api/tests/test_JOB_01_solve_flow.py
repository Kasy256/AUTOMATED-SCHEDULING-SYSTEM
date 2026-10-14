import threading

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import (
    add_member,
    build_schedule,
    drain_solves,
    parse_sse,
    request_run,
    run_now,
    running_worker,
    signup_and_confirm,
    solve_now,
    worker_env,
)

pytestmark = pytest.mark.integration


def test_JOB_01_actor_runs_solve_through_redis(
    client: TestClient, app: FastAPI, redis_url: str, monkeypatch: pytest.MonkeyPatch
) -> None:
    worker_env(monkeypatch, app.state.settings)
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    with running_worker(redis_url, threads=1) as broker:
        run_id = request_run(client, admin, built.schedule_id)
        drain_solves(broker)
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert (run["status"], run["error"]) == ("succeeded", None)
    assert run["version_id"] is not None


def test_JOB_01_post_solve_then_stream_progress_and_completion(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)
    worker = threading.Thread(target=run_now, args=(app, run_id, admin.organisation_id))
    worker.start()
    try:
        with client.stream("GET", f"/api/v1/solves/{run_id}/events", headers=admin.auth) as r:
            assert r.headers["content-type"].startswith("text/event-stream")
            assert r.headers["cache-control"] == "no-store"
            events = parse_sse(r.iter_lines())
    finally:
        worker.join(timeout=60)
    assert events[-1].event == "done"
    assert events[-1].data["status"] == "succeeded" and events[-1].data["version_id"]
    assert any(e.event == "progress" for e in events)
    assert [e.event for e in events].count("done") == 1


def test_JOB_01_stream_of_finished_run_sends_done_immediately(
    client: TestClient, app: FastAPI
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id, version_id = solve_now(client, admin, built.schedule_id)
    with client.stream("GET", f"/api/v1/solves/{run_id}/events", headers=admin.auth) as r:
        events = parse_sse(r.iter_lines())
    assert [e.event for e in events] == ["progress", "done"]
    assert events[1].data == {"status": "succeeded", "version_id": version_id, "error": None}


def test_JOB_01_stream_of_other_orgs_run_is_404(client: TestClient, app: FastAPI) -> None:
    a = signup_and_confirm(client, app, org_name="Stream A")
    b = signup_and_confirm(client, app, org_name="Stream B")
    run_id, _ = solve_now(client, a, build_schedule(client, a).schedule_id)
    response = client.get(f"/api/v1/solves/{run_id}/events", headers=b.auth)
    assert response.status_code == 404
    assert response.headers["content-type"].startswith("application/problem+json")


def test_JOB_01_member_cannot_stream(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    run_id, _ = solve_now(client, admin, build_schedule(client, admin).schedule_id)
    member = add_member(client, app, admin, ["member"])
    response = client.get(f"/api/v1/solves/{run_id}/events", headers=member.auth)
    assert response.status_code == 403
