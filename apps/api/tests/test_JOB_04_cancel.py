import threading
import time
from typing import Any

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from support import fetch, request_run, run_now, signup_and_confirm, slow_schedule, superuser_url

pytestmark = pytest.mark.integration

# Generous: the first progress needs the model compiled and a first schedule constructed.
_START_TIMEOUT_S = 60


def test_JOB_04_cancel_running_solve_within_5_seconds(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = slow_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id, time_limit_s=60)
    result: list[str] = []
    worker = threading.Thread(
        target=lambda: result.append(run_now(app, run_id, admin.organisation_id))
    )
    worker.start()
    deadline = time.monotonic() + _START_TIMEOUT_S
    # Any: JSON response body.
    run: dict[str, Any] = {}
    while time.monotonic() < deadline:
        run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
        if run["status"] == "running" and run["progress"]:
            break
        time.sleep(0.2)
    assert run["status"] == "running" and run["progress"], run
    cancelled_at = time.monotonic()
    assert client.post(f"/api/v1/solves/{run_id}/cancel", headers=admin.auth).status_code == 202
    worker.join(timeout=5)
    assert not worker.is_alive(), "worker still solving 5 s after cancel"
    assert time.monotonic() - cancelled_at < 5
    assert result == ["cancelled"]
    final = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert final["status"] == "cancelled" and final["finished_at"] is not None


def test_JOB_04_time_limited_run_returns_best_so_far(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = slow_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id, time_limit_s=1)
    assert run_now(app, run_id, admin.organisation_id) == "succeeded"
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT status, solver_status, (SELECT count(*) FROM assignment a "
        f"WHERE a.version_id = v.id) FROM solution_version v WHERE id = '{run['version_id']}'",
    )
    # FEASIBLE, not OPTIMAL: the limit ended the search and the best plan so far was kept.
    assert rows == [("draft", "FEASIBLE", built.activities)]
