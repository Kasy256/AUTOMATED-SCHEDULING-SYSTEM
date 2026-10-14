import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.main import create_app
from cartlyf_engine.domain import Problem, Solution, SolveOptions
from cartlyf_engine.solve import CancelToken, ProgressFn
from support import (
    APP,
    Account,
    build_schedule,
    db_url,
    execute,
    make_settings,
    request_run,
    run_now,
    signup_and_confirm,
    superuser_url,
)

pytestmark = pytest.mark.integration


def _must_not_be_called(
    problem: Problem,
    options: SolveOptions | None,
    on_progress: ProgressFn | None,
    cancel: CancelToken | None,
) -> Solution:
    raise AssertionError("solved a run whose worker had already died")


def _running(pg: PostgresContainer, run_id: str, age_s: int) -> None:
    execute(
        superuser_url(pg),
        "UPDATE solve_run SET status = 'running', started_at = now() - interval '5 minutes', "
        f"heartbeat_at = now() - interval '{age_s} seconds' WHERE id = '{run_id}'",
    )


def _status(client: TestClient, admin: Account, run_id: str) -> dict[str, object]:
    return client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()


def _queued(client: TestClient, app: FastAPI) -> tuple[Account, str]:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    return admin, request_run(client, admin, built.schedule_id)


def test_JOB_05_stale_running_run_becomes_failed(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin, run_id = _queued(client, app)
    _running(migrated_pg, run_id, 31)
    run = _status(client, admin, run_id)
    assert (run["status"], run["error"]) == ("failed", "worker stopped responding")


def test_JOB_05_redelivered_message_fails_stale_run_without_solving(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin, run_id = _queued(client, app)
    _running(migrated_pg, run_id, 31)
    assert run_now(app, run_id, admin.organisation_id, solve_fn=_must_not_be_called) == "skipped"
    assert _status(client, admin, run_id)["status"] == "failed"


def test_JOB_05_fresh_running_run_is_left_alone(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin, run_id = _queued(client, app)
    _running(migrated_pg, run_id, 0)
    assert _status(client, admin, run_id)["status"] == "running"
    assert run_now(app, run_id, admin.organisation_id, solve_fn=_must_not_be_called) == "skipped"
    assert _status(client, admin, run_id)["status"] == "running"


def test_JOB_05_crash_frees_the_cap_slot(
    migrated_pg: PostgresContainer, redis_url: str, minio_settings: dict[str, object]
) -> None:
    capped = create_app(
        make_settings(
            db_url(migrated_pg, *APP),
            redis_url,
            solve_num_workers=1,
            solve_max_concurrent_per_org=1,
            **minio_settings,
        )
    )
    with TestClient(capped, raise_server_exceptions=False) as client:
        admin = signup_and_confirm(client, capped)
        built = build_schedule(client, admin)
        url = f"/api/v1/schedules/{built.schedule_id}/solves"
        first = client.post(url, headers=admin.auth, json={})
        assert first.status_code == 202
        assert client.post(url, headers=admin.auth, json={}).status_code == 429
        _running(migrated_pg, first.json()["id"], 31)
        assert client.post(url, headers=admin.auth, json={}).status_code == 202
        assert _status(client, admin, first.json()["id"])["status"] == "failed"
