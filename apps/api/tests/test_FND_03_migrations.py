import pytest
from alembic import command
from sqlalchemy.exc import ProgrammingError
from testcontainers.community.postgres import PostgresContainer

from support import APP, OWNER, alembic_config, db_url, execute, fetch

pytestmark = pytest.mark.integration
EXTENSIONS = {"citext", "btree_gist"}


def _extensions(url: str) -> set[str]:
    return {row[0] for row in fetch(url, "SELECT extname FROM pg_extension")}


def _default_acl_types(url: str) -> set[str]:
    sql = (
        "SELECT d.defaclobjtype::text FROM pg_default_acl d "
        "JOIN pg_roles r ON r.oid = d.defaclrole WHERE r.rolname = 'cartlyf_owner'"
    )
    return {row[0] for row in fetch(url, sql)}


def test_FND_03_roles_are_unprivileged(pg: PostgresContainer) -> None:
    rows = fetch(
        db_url(pg, *OWNER),
        "SELECT rolname, rolsuper, rolbypassrls, rolcreaterole FROM pg_roles "
        "WHERE rolname IN ('cartlyf_owner', 'cartlyf_app') ORDER BY rolname",
    )
    assert [tuple(r) for r in rows] == [
        ("cartlyf_app", False, False, False),
        ("cartlyf_owner", False, False, False),
    ]


def test_FND_03_baseline_upgrades_and_downgrades_as_owner(pg: PostgresContainer) -> None:
    owner_url = db_url(pg, *OWNER)
    config = alembic_config(owner_url)

    command.upgrade(config, "head")
    assert _extensions(owner_url) >= EXTENSIONS
    assert _default_acl_types(owner_url) == {"r", "S"}
    version_owner = fetch(
        owner_url, "SELECT tableowner FROM pg_tables WHERE tablename = 'alembic_version'"
    )
    assert version_owner[0][0] == "cartlyf_owner"

    command.downgrade(config, "base")
    assert not (EXTENSIONS & _extensions(owner_url))
    assert _default_acl_types(owner_url) == set()

    command.upgrade(config, "head")


def test_FND_03_app_role_dml_only(migrated_pg: PostgresContainer) -> None:
    owner_url, app_url = db_url(migrated_pg, *OWNER), db_url(migrated_pg, *APP)
    execute(owner_url, "CREATE TABLE fnd03_probe (id int)")
    try:
        execute(app_url, "INSERT INTO fnd03_probe VALUES (1)")
        assert fetch(app_url, "SELECT id FROM fnd03_probe")[0][0] == 1
        with pytest.raises(ProgrammingError, match="permission denied"):
            execute(app_url, "CREATE TABLE fnd03_forbidden (id int)")
    finally:
        execute(owner_url, "DROP TABLE fnd03_probe")
