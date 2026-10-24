from uuid import uuid4

import pytest
from sqlalchemy.exc import IntegrityError
from testcontainers.community.postgres import PostgresContainer

from support import OWNER, db_url, execute, seed_org, superuser_url

pytestmark = pytest.mark.integration


def test_cross_org_reference_is_impossible(migrated_pg: PostgresContainer) -> None:
    url = superuser_url(migrated_pg)
    a = seed_org(url, "Schema A")
    b = seed_org(url, "Schema B")
    type_b = uuid4()
    execute(
        url,
        "INSERT INTO resource_type (id, organisation_id, key, name, kind, attribute_schema) "
        f"VALUES ('{type_b}', '{b.organisation_id}', 'room', 'Room', 'space', '{{}}')",
    )
    with pytest.raises(IntegrityError, match="foreign key"):
        execute(
            url,
            "INSERT INTO resource (id, organisation_id, resource_type_id, code, name) "
            f"VALUES ('{uuid4()}', '{a.organisation_id}', '{type_b}', 'R1', 'Room 1')",
        )


def test_codes_are_unique_among_live_resources_only(migrated_pg: PostgresContainer) -> None:
    url = superuser_url(migrated_pg)
    org = seed_org(url, "Schema Codes")
    type_id = uuid4()
    execute(
        url,
        "INSERT INTO resource_type (id, organisation_id, key, name, kind, attribute_schema) "
        f"VALUES ('{type_id}', '{org.organisation_id}', 'room', 'Room', 'space', '{{}}')",
    )
    insert = (
        "INSERT INTO resource (id, organisation_id, resource_type_id, code, name, deleted_at) "
        f"VALUES ('{{id}}', '{org.organisation_id}', '{type_id}', 'R1', 'Room 1', {{deleted}})"
    )
    execute(url, insert.format(id=uuid4(), deleted="now()"))
    execute(url, insert.format(id=uuid4(), deleted="NULL"))
    with pytest.raises(IntegrityError, match="resource_org_code_live_idx"):
        execute(url, insert.format(id=uuid4(), deleted="NULL"))


def test_migration_downgrades_cleanly(migrated_pg: PostgresContainer) -> None:
    from alembic import command

    from support import alembic_config

    config = alembic_config(db_url(migrated_pg, *OWNER))
    command.downgrade(config, "0002")
    command.upgrade(config, "head")
