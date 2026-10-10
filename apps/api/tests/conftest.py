from collections.abc import Iterator

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.minio import MinioContainer
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.main import create_app
from support import APP, OWNER, alembic_config, apply_roles, db_url, make_settings

# Community fork: upstream MinIO images are no longer published on Docker Hub.
MINIO_IMAGE = "pgsty/minio:RELEASE.2026-08-04T00-00-00Z"
TEST_BUCKET = "cartlyf-test"


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresContainer]:
    # Durability off: WAL fsync on some Docker hosts stalls COMMIT for seconds, past the
    # app's DB timeout. Crash safety is irrelevant to a throwaway test database.
    container = PostgresContainer("postgres:16-alpine").with_command(
        "postgres -c fsync=off -c synchronous_commit=off -c full_page_writes=off"
    )
    with container:
        apply_roles(container)
        yield container


@pytest.fixture(scope="session")
def migrated_pg(pg: PostgresContainer) -> PostgresContainer:
    command.upgrade(alembic_config(db_url(pg, *OWNER)), "head")
    return pg


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer("redis:7-alpine") as container:
        yield container


@pytest.fixture
def redis_url(redis_container: RedisContainer) -> str:
    redis_container.get_client().flushdb()  # pyright: ignore[reportUnknownMemberType]
    host = redis_container.get_container_host_ip()
    port = redis_container.get_exposed_port(redis_container.port)
    return f"redis://{host}:{port}/0"


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def minio_settings() -> Iterator[dict[str, object]]:
    with MinioContainer(MINIO_IMAGE) as container:
        container.get_client().make_bucket(TEST_BUCKET)
        host = container.get_container_host_ip()
        port = container.get_exposed_port(container.port)
        yield {
            "s3_endpoint": f"{host}:{port}",
            "s3_access_key": container.access_key,
            "s3_secret_key": container.secret_key,
            "s3_bucket": TEST_BUCKET,
            "s3_secure": False,
        }


@pytest.fixture
def app(
    migrated_pg: PostgresContainer, redis_url: str, minio_settings: dict[str, object]
) -> FastAPI:
    return create_app(make_settings(db_url(migrated_pg, *APP), redis_url, **minio_settings))
