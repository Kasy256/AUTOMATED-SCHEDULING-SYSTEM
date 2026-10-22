"""Healthcare roster built through the product: template -> staff import -> leave -> demands.

The renamed snapshot is pinned as the engine roster fixture; set CARTLYF_WRITE_FIXTURES=1 to
rewrite it after an intended change to the template, the import or the demand shapes.
"""

import asyncio
import json
import os
from collections.abc import Iterator
from pathlib import Path
from uuid import UUID

import pytest
from fastapi.testclient import TestClient
from healthcare import build_roster, staff_csv
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.main import create_app
from cartlyf_api.problems.snapshot import build_snapshot
from cartlyf_api.tenancy import scoped_transaction
from cartlyf_engine.domain import Problem
from support import APP, Account, db_url, make_settings, renamed

pytestmark = pytest.mark.integration

PROBLEM_FILE = (
    Path(__file__).resolve().parents[3]
    / "packages/engine/tests/fixtures/healthcare/v1/roster_problem.json"
)


def _snapshot(pg: PostgresContainer, admin: Account, schedule_id: str) -> Problem:
    async def run() -> Problem:
        engine = create_async_engine(db_url(pg, *APP))
        try:
            async with scoped_transaction(engine, admin.organisation_id) as session:
                snap = await build_snapshot(session, admin.organisation_id, UUID(schedule_id))
                return snap.problem
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _canonical(problem: Problem) -> str:
    return json.dumps(problem.model_dump(mode="json"), indent=1, sort_keys=True) + "\n"


@pytest.fixture(scope="module")
def roster(
    migrated_pg: PostgresContainer,
    redis_container: RedisContainer,
    minio_settings: dict[str, object],
) -> Iterator[Problem]:
    redis_container.get_client().flushdb()  # pyright: ignore[reportUnknownMemberType]
    host = redis_container.get_container_host_ip()
    redis_url = f"redis://{host}:{redis_container.get_exposed_port(redis_container.port)}/0"
    app = create_app(make_settings(db_url(migrated_pg, *APP), redis_url, **minio_settings))
    with TestClient(app, raise_server_exceptions=False) as client:
        built = build_roster(client)
        problem = renamed(_snapshot(migrated_pg, built.admin, built.schedule_id), built.names)
    if os.environ.get("CARTLYF_WRITE_FIXTURES") == "1":
        PROBLEM_FILE.parent.mkdir(parents=True, exist_ok=True)
        PROBLEM_FILE.write_text(_canonical(problem), encoding="utf-8", newline="\n")
    yield problem


def test_staff_csv_is_seeded() -> None:
    assert staff_csv(8) == staff_csv(8)
    assert staff_csv(8) != staff_csv(9)


def test_HC_roster_shape(roster: Problem) -> None:
    assert len(roster.activities) == 28 * 3 * 2 + 28 * 3
    assert len(roster.resources) == 40
    assert sum(1 for r in roster.resources if "RN" in r.tags) == 24
    assert sum(1 for r in roster.resources if "midwife" in r.tags) == 11
    assert sum(1 for r in roster.resources if r.unavailable) == 3


def test_HC_roster_fixture_is_current(roster: Problem) -> None:
    assert PROBLEM_FILE.exists(), "run once with CARTLYF_WRITE_FIXTURES=1"
    assert PROBLEM_FILE.read_text(encoding="utf-8") == _canonical(roster), (
        "roster_problem.json is stale: rerun with CARTLYF_WRITE_FIXTURES=1"
    )
