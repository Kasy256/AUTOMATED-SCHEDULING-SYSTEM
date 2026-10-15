import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_engine.domain import Problem, Solution, SolveOptions
from cartlyf_engine.solve import CancelToken, ProgressFn, solve
from support import (
    CollectingTransport,
    build_schedule,
    fetch,
    request_run,
    run_now,
    signup_and_confirm,
    superuser_url,
)

pytestmark = pytest.mark.integration


def test_JOB_02_verified_result_becomes_draft(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin, lecturers=2, rooms=2, demands=2)
    run_id = request_run(client, admin, built.schedule_id)
    assert run_now(app, run_id, admin.organisation_id) == "succeeded"
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert run["status"] == "succeeded" and run["finished_at"] is not None
    db = superuser_url(migrated_pg)
    version = fetch(
        db,
        "SELECT status, number, (score->>'hard_violations')::int, solve_run_id::text, "
        f"(SELECT count(*) FROM assignment a WHERE a.version_id = v.id) "
        f"FROM solution_version v WHERE id = '{run['version_id']}'",
    )
    assert version == [("draft", 1, 0, run_id, built.activities)]
    spans = fetch(
        db,
        "SELECT DISTINCT end_at - start_at FROM assignment "
        f"WHERE version_id = '{run['version_id']}'",
    )
    assert [str(span) for (span,) in spans] == ["1:00:00"]
    roles = fetch(
        db,
        "SELECT role, count(*) FROM assignment_resource "
        f"WHERE version_id = '{run['version_id']}' GROUP BY role ORDER BY role",
    )
    assert roles == [(role, built.activities) for role in ("group", "lecturer", "room")]


def test_versions_are_numbered_per_schedule(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    numbers: list[int] = []
    for _ in range(2):
        run_id = request_run(client, admin, built.schedule_id)
        assert run_now(app, run_id, admin.organisation_id) == "succeeded"
        version_id = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()["version_id"]
        numbers += [
            n
            for (n,) in fetch(
                superuser_url(migrated_pg),
                f"SELECT number FROM solution_version WHERE id = '{version_id}'",
            )
        ]
    assert numbers == [1, 2]


def test_JOB_02_forced_disagreement_marks_failed_verification(
    client: TestClient,
    app: FastAPI,
    migrated_pg: PostgresContainer,
    capture_sentry: CollectingTransport,
) -> None:
    admin = signup_and_confirm(client, app)
    built = build_schedule(client, admin)
    run_id = request_run(client, admin, built.schedule_id)

    def lying_solve(
        problem: Problem,
        options: SolveOptions | None,
        on_progress: ProgressFn | None,
        cancel: CancelToken | None,
    ) -> Solution:
        real = solve(problem, options, None, cancel)
        broken = tuple(a.model_copy(update={"resources": {}}) for a in real.assignments)
        return real.model_copy(update={"assignments": broken})  # still claims the clean score

    assert run_now(app, run_id, admin.organisation_id, solve_fn=lying_solve) == (
        "failed_verification"
    )
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    assert (run["status"], run["error"], run["version_id"]) == (
        "failed_verification",
        "The result failed verification",
        None,
    )
    versions = fetch(
        superuser_url(migrated_pg),
        f"SELECT count(*) FROM solution_version WHERE schedule_id = '{built.schedule_id}'",
    )
    assert versions == [(0,)]
    assert capture_sentry.messages == ["solve_failed_verification"]
    assert capture_sentry.tags == [
        {"run_id": run_id, "organisation_id": str(admin.organisation_id)}
    ]
