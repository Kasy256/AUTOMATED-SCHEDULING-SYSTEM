import asyncio
from typing import Any, cast
from uuid import UUID

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.db import create_db_engine
from cartlyf_api.settings import Settings
from cartlyf_api.solves.runner import execute_run
from cartlyf_engine.domain import Problem, Solution, SolveOptions
from cartlyf_engine.solve import CancelToken, ProgressFn, solve
from support import (
    APP,
    Account,
    CollectingTransport,
    add_rule,
    build_schedule,
    execute,
    fetch,
    request_run,
    run_now,
    signup_and_confirm,
    superuser_url,
)

pytestmark = pytest.mark.integration


# Any: JSON response body.
def _run(client: TestClient, admin: Account, run_id: str) -> dict[str, Any]:
    return client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()


def _never(
    problem: Problem,
    options: SolveOptions | None,
    on_progress: ProgressFn | None,
    cancel: CancelToken | None,
) -> Solution:
    raise AssertionError("solved a run that was not queued")


def test_infeasible_run_stores_conflicts(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    rule = add_rule(
        client,
        admin,
        built.schedule_id,
        "max_load",
        {"period": "day", "max_count": 0},
        hard=True,
        scope={"resource_ids": built.lecturer_ids},
    )
    run_id = request_run(client, admin, built.schedule_id)
    assert run_now(app, run_id, admin.organisation_id) == "infeasible"
    run = _run(client, admin, run_id)
    assert run["status"] == "infeasible" and run["version_id"] is None
    assert rule in run["conflicts"]


def test_unsupported_template_fails_cleanly(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    add_rule(
        client,
        admin,
        built.schedule_id,
        "stability",
        {"per_change": 1, "per_resource_change": 1},
        weight=1,
    )
    run_id = request_run(client, admin, built.schedule_id)
    assert run_now(app, run_id, admin.organisation_id) == "failed"
    assert _run(client, admin, run_id)["error"] == "Rule 'stability' is not supported yet"


def test_solver_crash_is_reported_without_internals(
    client: TestClient, app: FastAPI, capture_sentry: CollectingTransport
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)

    def crash(
        problem: Problem,
        options: SolveOptions | None,
        on_progress: ProgressFn | None,
        cancel: CancelToken | None,
    ) -> Solution:
        raise RuntimeError("secret internal detail")

    assert run_now(app, run_id, admin.organisation_id, solve_fn=crash) == "failed"
    run = _run(client, admin, run_id)
    assert run["error"] == "The solver stopped unexpectedly"
    assert len(capture_sentry.events) == 1
    assert capture_sentry.tags == [
        {"run_id": run_id, "organisation_id": str(admin.organisation_id)}
    ]


def test_progress_written_and_notified(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=2, rooms=2, demands=2)
    run_id = request_run(client, admin, built.schedule_id)
    settings: Settings = app.state.settings
    host, port = migrated_pg.get_container_host_ip(), int(migrated_pg.get_exposed_port(5432))

    async def go() -> tuple[str, list[str]]:
        heard: list[str] = []
        # Any: asyncpg ships no type stubs.
        conn = cast(
            Any,
            await asyncpg.connect(  # pyright: ignore[reportUnknownMemberType]
                user=APP[0], password=APP[1], host=host, port=port, database="cartlyf"
            ),
        )

        def on_notify(*args: object) -> None:
            heard.append(str(args[3]))

        await conn.add_listener("solve_run", on_notify)
        engine = create_db_engine(settings)
        try:
            status = await execute_run(engine, settings, UUID(run_id), admin.organisation_id)
            await asyncio.sleep(0.2)
            return status, heard
        finally:
            await engine.dispose()
            await conn.close()

    status, heard = asyncio.run(go())
    assert status == "succeeded"
    assert heard and set(heard) == {run_id}
    progress = _run(client, admin, run_id)["progress"]
    assert progress["kind"] in {"solution", "constructed", "bound"}
    assert set(progress) == {"kind", "objective", "best_bound", "solutions", "wall_time_s"}


def test_TEN_04_worker_cannot_run_other_orgs_run(client: TestClient, app: FastAPI) -> None:
    a = signup_and_confirm(client, app, org_name="Runner A")
    b = signup_and_confirm(client, app, org_name="Runner B")
    built = build_schedule(client, b)
    run_id = request_run(client, b, built.schedule_id)
    assert run_now(app, run_id, a.organisation_id, solve_fn=_never) == "skipped"
    assert _run(client, b, run_id)["status"] == "queued"


def test_finished_run_is_not_solved_again(client: TestClient, app: FastAPI) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)
    client.post(f"/api/v1/solves/{run_id}/cancel", headers=admin.auth)
    assert run_now(app, run_id, admin.organisation_id, solve_fn=_never) == "skipped"
    assert _run(client, admin, run_id)["status"] == "cancelled"


def test_redelivered_running_run_is_skipped_and_stale_one_failed(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    fresh = request_run(client, admin, built.schedule_id)
    stale = request_run(client, admin, built.schedule_id)
    db = superuser_url(migrated_pg)
    execute(
        db,
        "UPDATE solve_run SET status = 'running', started_at = now(), heartbeat_at = now() "
        f"WHERE id = '{fresh}'",
    )
    execute(
        db,
        "UPDATE solve_run SET status = 'running', started_at = now(), "
        f"heartbeat_at = now() - interval '5 minutes' WHERE id = '{stale}'",
    )
    for run_id in (fresh, stale):
        assert run_now(app, run_id, admin.organisation_id, solve_fn=_never) == "skipped"
    statuses = fetch(
        db, f"SELECT id::text, status FROM solve_run WHERE id IN ('{fresh}', '{stale}')"
    )
    assert dict(statuses) == {fresh: "running", stale: "failed"}


def test_run_failed_by_sweep_mid_solve_is_not_overwritten(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)
    db = superuser_url(migrated_pg)

    def swept_solve(
        problem: Problem,
        options: SolveOptions | None,
        on_progress: ProgressFn | None,
        cancel: CancelToken | None,
    ) -> Solution:
        execute(db, f"UPDATE solve_run SET status = 'failed' WHERE id = '{run_id}'")
        return solve(problem, options, on_progress, cancel)

    assert run_now(app, run_id, admin.organisation_id, solve_fn=swept_solve) == "failed"
    assert fetch(db, f"SELECT status, version_id FROM solve_run WHERE id = '{run_id}'") == [
        ("failed", None)
    ]
    versions = fetch(db, f"SELECT count(*) FROM solution_version WHERE solve_run_id = '{run_id}'")
    assert versions == [(0,)]
