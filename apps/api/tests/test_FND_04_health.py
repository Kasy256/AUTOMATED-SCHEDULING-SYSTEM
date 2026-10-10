import pytest
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.main import create_app
from cartlyf_api.settings import Settings
from support import APP, db_url


def _client(database_url: str) -> TestClient:
    settings = Settings.model_validate(
        {"database_url": database_url, "redis_url": "redis://localhost:1/0"}
    )
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


def test_health_db_unreachable_is_503_problem() -> None:
    with _client("postgresql+asyncpg://cartlyf_app:x@127.0.0.1:1/cartlyf") as client:
        response = client.get("/api/v1/health")
    assert response.status_code == 503
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json()["title"] == "Database unavailable"
    assert "Traceback" not in response.text
