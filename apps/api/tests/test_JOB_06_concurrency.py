import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import (
    build_schedule,
    drain_solves,
    fetch,
    request_run,
    running_worker,
    signup_and_confirm,
    superuser_url,
    worker_env,
)

pytestmark = pytest.mark.integration


def test_JOB_06_two_orgs_solve_concurrently(
    client: TestClient,
    app: FastAPI,
    redis_url: str,
    migrated_pg: PostgresContainer,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    worker_env(monkeypatch, app.state.settings)
    a = signup_and_confirm(client, app, org_name="Concurrent A")
    b = signup_and_confirm(client, app, org_name="Concurrent B")
    built_a = build_schedule(client, a)
    built_b = build_schedule(client, b)
    with running_worker(redis_url, threads=2) as broker:
        run_a = request_run(client, a, built_a.schedule_id)
        run_b = request_run(client, b, built_b.schedule_id)
        drain_solves(broker)
    runs = {}
    for admin, run_id in ((a, run_a), (b, run_b)):
        run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
        assert (run["status"], run["error"]) == ("succeeded", None)
        runs[run_id] = run["version_id"]
    db = superuser_url(migrated_pg)
    for run_id, admin in ((run_a, a), (run_b, b)):
        used = {
            str(r)
            for (r,) in fetch(
                db,
                "SELECT DISTINCT resource_id FROM assignment_resource "
                f"WHERE version_id = '{runs[run_id]}'",
            )
        }
        own = {
            str(r)
            for (r,) in fetch(
                db, f"SELECT id FROM resource WHERE organisation_id = '{admin.organisation_id}'"
            )
        }
        assert used and used <= own
    assert client.get(f"/api/v1/solves/{run_b}", headers=a.auth).status_code == 404
    assert client.get(f"/api/v1/solves/{run_a}", headers=b.auth).status_code == 404
