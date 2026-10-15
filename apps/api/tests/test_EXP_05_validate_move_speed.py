import random
import time
from collections.abc import Iterator
from datetime import datetime, timedelta

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from isbat import build_term1
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.main import create_app
from support import APP, db_url, get_version, make_settings, request_run, run_now

pytestmark = pytest.mark.integration


@pytest.fixture(scope="module")
def isbat_app(
    migrated_pg: PostgresContainer,
    redis_container: RedisContainer,
    minio_settings: dict[str, object],
) -> Iterator[FastAPI]:
    redis_container.get_client().flushdb()  # pyright: ignore[reportUnknownMemberType]
    host = redis_container.get_container_host_ip()
    redis_url = f"redis://{host}:{redis_container.get_exposed_port(redis_container.port)}/0"
    yield create_app(make_settings(db_url(migrated_pg, *APP), redis_url, **minio_settings))


def test_EXP_05_validate_move_p95_under_200ms_on_isbat(isbat_app: FastAPI) -> None:
    with TestClient(isbat_app, raise_server_exceptions=False) as client:
        built = build_term1(client)
        admin = built.admin
        run_id = request_run(client, admin, built.schedule_id, time_limit_s=20)
        assert run_now(isbat_app, run_id, admin.organisation_id) == "succeeded"
        version_id = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()["version_id"]
        assignments = get_version(client, admin, version_id)["assignments"]
        url = f"/api/v1/solution-versions/{version_id}/validate-move"
        rng = random.Random(0)
        times: list[float] = []
        for _ in range(100):
            placed = rng.choice(assignments)
            shift = timedelta(days=rng.choice((-1, 0, 1)))
            body = {
                "activity_id": placed["activity_id"],
                "start_at": (datetime.fromisoformat(placed["start_at"]) + shift).isoformat(),
                "resources": placed["resources"],
            }
            began = time.perf_counter()
            response = client.post(url, headers=admin.auth, json=body)
            times.append(time.perf_counter() - began)
            assert response.status_code in (200, 422), response.text
    times.sort()
    assert times[int(0.95 * len(times))] < 0.2
