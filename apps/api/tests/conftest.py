from collections.abc import Iterator

import pytest
from alembic import command
from fastapi import FastAPI
from fastapi.testclient import TestClient
from testcontainers.community.postgres import PostgresContainer
from testcontainers.community.redis import RedisContainer

from cartlyf_api.main import create_app
from support import APP, OWNER, alembic_config, apply_roles, db_url, make_settings


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as container:
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
def app(migrated_pg: PostgresContainer, redis_url: str) -> FastAPI:
    return create_app(make_settings(db_url(migrated_pg, *APP), redis_url))


@pytest.fixture
def client(app: FastAPI) -> Iterator[TestClient]:
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client
