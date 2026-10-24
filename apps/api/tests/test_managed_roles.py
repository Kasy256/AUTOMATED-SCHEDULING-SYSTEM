"""managed_roles.sql provisions a managed Postgres (e.g. Render) whose admin is not a superuser."""

from collections.abc import Iterator

import pytest
from alembic import command
from testcontainers.community.postgres import PostgresContainer

from support import API_DIR, APP, OWNER, alembic_config, db_url, fetch

pytestmark = pytest.mark.integration
ADMIN = ("cartlyf_admin", "admin-test-password")


@pytest.fixture(scope="module")
def managed_pg() -> Iterator[PostgresContainer]:
    with PostgresContainer("postgres:16-alpine") as container:
        # What the host creates: a database owned by a non-superuser admin.
        for statement in (
            f"CREATE ROLE {ADMIN[0]} LOGIN PASSWORD '{ADMIN[1]}' CREATEDB CREATEROLE",
            f"CREATE DATABASE cartlyf OWNER {ADMIN[0]}",
        ):
            code, output = container.exec(
                ["psql", "-U", container.username, "-d", "postgres", "-c", statement]
            )
            assert code == 0, repr(output)
        sql = (API_DIR / "db" / "managed_roles.sql").read_text(encoding="utf-8")
        script = (
            'printf "%s" "$1" | PGPASSWORD="$3" psql -h 127.0.0.1 -U "$2" -d cartlyf '
            '-v owner_password="$4" -v app_password="$5" -f -'
        )
        code, output = container.exec(
            ["sh", "-c", script, "sh", sql, ADMIN[0], ADMIN[1], OWNER[1], APP[1]]
        )
        assert code == 0, repr(output)
        yield container


def test_managed_roles_are_unprivileged(managed_pg: PostgresContainer) -> None:
    rows = fetch(
        db_url(managed_pg, *ADMIN),
        "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole, rolcreatedb FROM pg_roles "
        "WHERE rolname IN ('cartlyf_owner', 'cartlyf_app') ORDER BY rolname",
    )
    assert rows == [
        ("cartlyf_app", False, False, False, False),
        ("cartlyf_owner", False, False, False, False),
    ]


def test_migrations_run_as_owner_and_app_is_confined(managed_pg: PostgresContainer) -> None:
    command.upgrade(alembic_config(db_url(managed_pg, *OWNER)), "head")
    app_url = db_url(managed_pg, *APP)
    assert fetch(app_url, "SELECT count(*) FROM organisation") == [(0,)]
    assert fetch(app_url, "SELECT has_database_privilege('cartlyf', 'CREATE')") == [(False,)]
    extensions = {row[0] for row in fetch(app_url, "SELECT extname FROM pg_extension")}
    assert {"citext", "btree_gist"} <= extensions
