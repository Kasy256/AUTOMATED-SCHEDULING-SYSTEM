import time

import pytest
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.main import create_app
from support import APP, db_url, execute, make_settings


def _client(database_url: str, **overrides: object) -> TestClient:
    settings = make_settings(database_url, "redis://localhost:1/0", **overrides)
    return TestClient(create_app(settings), raise_server_exceptions=False)


@pytest.mark.integration
def test_FND_04_health_connects_as_unprivileged_app_role(migrated_pg: PostgresContainer) -> None:
    with _client(db_url(migrated_pg, *APP)) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 200
    assert response.json() == {
        "status": "ok",
        "database": {"current_user": "cartlyf_app", "rolsuper": False, "rolbypassrls": False},
    }


@pytest.mark.integration
def test_FND_04_health_rejects_superuser(migrated_pg: PostgresContainer) -> None:
    superuser = db_url(migrated_pg, migrated_pg.username, migrated_pg.password)
    with _client(superuser) as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Unsafe database role"


@pytest.mark.integration
def test_FND_04_health_rejects_bypassrls_role(migrated_pg: PostgresContainer) -> None:
    superuser = db_url(migrated_pg, migrated_pg.username, migrated_pg.password)
    execute(superuser, "CREATE ROLE fnd04_bypass LOGIN PASSWORD 'bypass-pw' NOSUPERUSER BYPASSRLS")
    execute(superuser, "GRANT CONNECT ON DATABASE cartlyf TO fnd04_bypass")
    try:
        with _client(db_url(migrated_pg, "fnd04_bypass", "bypass-pw")) as client:
            response = client.get("/api/v1/health")
    finally:
        execute(superuser, "DROP OWNED BY fnd04_bypass")
        execute(superuser, "DROP ROLE fnd04_bypass")
    assert response.status_code == 503
    assert response.json()["title"] == "Unsafe database role"


def test_health_db_unreachable_is_503_problem() -> None:
    with _client("postgresql+asyncpg://cartlyf_app:x@127.0.0.1:1/cartlyf") as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Database unavailable"
    assert "Traceback" not in response.text


def test_health_db_blackholed_times_out_quickly() -> None:
    # 10.255.255.1 is non-routable: packets are dropped, so only a connect timeout ends the wait.
    with _client(
        "postgresql+asyncpg://cartlyf_app:x@10.255.255.1:5432/cartlyf",
        db_timeout_seconds=1,
    ) as client:
        started = time.monotonic()
        response = client.get("/api/v1/health")
        elapsed = time.monotonic() - started
    assert response.status_code == 503
    assert response.json()["title"] == "Database unavailable"
    assert elapsed < 5
