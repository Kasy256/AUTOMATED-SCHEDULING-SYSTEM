import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from support import (
    build_schedule,
    drain_solves,
    request_run,
    running_worker,
    signup_and_confirm,
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
