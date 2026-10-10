import pytest
from sqlalchemy.exc import DBAPIError
from testcontainers.community.postgres import PostgresContainer

from support import APP, db_url, execute, fetch, seed_org, superuser_url

pytestmark = pytest.mark.integration
TABLES = [
    "organisation",
    "app_user",
    "membership",
    "membership_role",
    "audit_log",
    "refresh_token",
    "email_outbox",
    "resource_type",
    "resource",
    "availability_rule",
    "availability_exception",
    "schedule",
    "slot_template",
    "demand",
    "activity",
    "requirement",
    "constraint_instance",
    "pin",
    "import_job",
]


@pytest.mark.parametrize("table", TABLES)
def test_TEN_02_no_context_sees_zero_rows(migrated_pg: PostgresContainer, table: str) -> None:
    seed_org(superuser_url(migrated_pg), "Ten02 Org")
    assert fetch(superuser_url(migrated_pg), f"SELECT count(*) FROM {table}")[0][0] > 0
    assert fetch(db_url(migrated_pg, *APP), f"SELECT count(*) FROM {table}")[0][0] == 0


def test_TEN_02_no_context_insert_into_tenant_table_denied(
    migrated_pg: PostgresContainer,
) -> None:
    seeded = seed_org(superuser_url(migrated_pg), "Ten02 Insert Org")
    with pytest.raises(DBAPIError, match="row-level security"):
        execute(
            db_url(migrated_pg, *APP),
            "INSERT INTO membership_role (organisation_id, membership_id, role) "
            f"VALUES ('{seeded.organisation_id}', '{seeded.membership_id}', 'viewer')",
        )
