import asyncio
import threading
import time
from typing import cast

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy.pool import QueuePool
from starlette.types import Message
from testcontainers.community.postgres import PostgresContainer

from support import (
    add_member,
    build_schedule,
    drain_solves,
    execute_many,
    parse_sse,
    request_run,
    run_now,
    running_worker,
    signup_and_confirm,
    solve_now,
    superuser_url,
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
    progress = [e for e in events if e.event == "progress"]
    assert any("status" in e.data and "kind" in e.data for e in progress)
    assert all("progress" not in e.data for e in progress)
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


def test_JOB_01_notify_wakes_stream_without_heartbeat_tick(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    app.state.settings = app.state.settings.model_copy(update={"solve_heartbeat_seconds": 30})
    admin = signup_and_confirm(client, app)
    run_id = request_run(client, admin, build_schedule(client, admin).schedule_id)
    finish = [
        f"UPDATE solve_run SET status = 'succeeded', finished_at = now() WHERE id = '{run_id}'",
        f"SELECT pg_notify('solve_run', '{run_id}')",
    ]
    timer = threading.Timer(2, execute_many, args=(superuser_url(migrated_pg), finish))
    timer.start()
    started = time.monotonic()
    try:
        with client.stream("GET", f"/api/v1/solves/{run_id}/events", headers=admin.auth) as r:
            events = parse_sse(r.iter_lines())
    finally:
        timer.join()
    assert events[-1].event == "done" and events[-1].data["status"] == "succeeded"
    assert time.monotonic() - started < 15


async def _abort_stream_after_first_event(app: FastAPI, path: str, headers: dict[str, str]) -> int:
    """Open a stream, read one event, then disconnect; returns pool checkouts while it was open."""
    first_event = asyncio.Event()
    scope = {
        "type": "http",
        "asgi": {"version": "3.0", "spec_version": "2.3"},
        "http_version": "1.1",
        "method": "GET",
        "scheme": "http",
        "path": path,
        "raw_path": path.encode(),
        "query_string": b"",
        "root_path": "",
        "headers": [(k.lower().encode(), v.encode()) for k, v in headers.items()],
        "client": ("testclient", 50000),
        "server": ("testserver", 80),
    }

    async def receive() -> Message:
        await first_event.wait()
        return {"type": "http.disconnect"}

    async def send(message: Message) -> None:
        if message["type"] == "http.response.body" and message.get("body"):
            first_event.set()

    task = asyncio.create_task(app(scope, receive, send))
    await asyncio.wait_for(first_event.wait(), 30)
    checked_out = cast(QueuePool, app.state.db_engine.pool).checkedout()
    await asyncio.wait_for(task, 30)
    return checked_out


def test_JOB_01_streams_hold_no_pooled_connection(client: TestClient, app: FastAPI) -> None:
    app.state.settings = app.state.settings.model_copy(update={"solve_heartbeat_seconds": 30})
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    finished, _ = solve_now(client, admin, built.schedule_id)
    queued = request_run(client, admin, built.schedule_id)
    for _ in range(3):
        with client.stream("GET", f"/api/v1/solves/{finished}/events", headers=admin.auth) as r:
            assert parse_sse(r.iter_lines())[-1].event == "done"
    queued_events = f"/api/v1/solves/{queued}/events"
    portal = client.portal
    assert portal is not None

    open_checkouts = portal.call(_abort_stream_after_first_event, app, queued_events, admin.auth)

    assert open_checkouts == 0
    assert cast(QueuePool, app.state.db_engine.pool).checkedout() == 0
    assert app.state.solve_notifier.subscriber_count() == 0
