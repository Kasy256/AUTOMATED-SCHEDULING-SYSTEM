from collections.abc import Iterator

import pytest
from alembic import command
from testcontainers.community.postgres import PostgresContainer

from support import OWNER, alembic_config, apply_roles, db_url


@pytest.fixture(scope="session")
def pg() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as container:
        apply_roles(container)
        yield container


@pytest.fixture(scope="session")
def migrated_pg(pg: PostgresContainer) -> PostgresContainer:
    command.upgrade(alembic_config(db_url(pg, *OWNER)), "head")
    return pg
