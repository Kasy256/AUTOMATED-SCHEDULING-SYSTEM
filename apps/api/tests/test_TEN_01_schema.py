import pytest
from testcontainers.community.postgres import PostgresContainer

from support import OWNER, db_url, execute, fetch, superuser_url

pytestmark = pytest.mark.integration

# Global by design: identity and the tenant root. Every other table must be tenant-scoped.
NON_TENANT_TABLES = {"organisation", "app_user", "refresh_token", "email_outbox"}
EXPECTED_DEFINER_FUNCTIONS = {"user_id_by_email", "refresh_token_user_id"}

_TABLES_SQL = """
SELECT c.relname, c.relrowsecurity, c.relforcerowsecurity,
       (SELECT count(*) FROM pg_policy p WHERE p.polrelid = c.oid)
FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'public' AND c.relkind IN ('r', 'p') AND c.relname <> 'alembic_version'
"""
_ORG_COLUMN_SQL = """
SELECT a.attnotnull, format_type(a.atttypid, a.atttypmod) FROM pg_attribute a
WHERE a.attrelid = 'public.{table}'::regclass AND a.attname = 'organisation_id'
  AND NOT a.attisdropped
"""
_INDEX_LEADS_SQL = """
SELECT i.indexrelid::regclass::text, a.attname, i.indisprimary FROM pg_index i
JOIN pg_attribute a ON a.attrelid = i.indrelid AND a.attnum = i.indkey[0]
WHERE i.indrelid = 'public.{table}'::regclass
"""


def tenancy_violations(url: str) -> list[str]:
    problems: list[str] = []
    for name, rls, forced, policies in fetch(url, _TABLES_SQL):
        if not (rls and forced):
            problems.append(f"{name}: RLS must be enabled and forced")
        if policies == 0:
            problems.append(f"{name}: has no RLS policy")
        if name in NON_TENANT_TABLES:
            continue
        column = fetch(url, _ORG_COLUMN_SQL.format(table=name))
        if not column or column[0][0] is not True or column[0][1] != "uuid":
            problems.append(f"{name}: needs organisation_id uuid NOT NULL")
        indexes = fetch(url, _INDEX_LEADS_SQL.format(table=name))
        # A single-column `id` primary key is exempt; every other index leads with the org.
        bad = [
            index for index, first, primary in indexes if first != "organisation_id" and not primary
        ]
        if bad:
            problems.append(f"{name}: indexes must lead with organisation_id: {bad}")
        if not any(first == "organisation_id" for _, first, _ in indexes):
            problems.append(f"{name}: needs an index leading with organisation_id")
    return problems


def test_TEN_01_every_table_is_tenant_safe(migrated_pg: PostgresContainer) -> None:
    assert tenancy_violations(superuser_url(migrated_pg)) == []


def test_TEN_01_checker_catches_an_unsafe_table(migrated_pg: PostgresContainer) -> None:
    owner = db_url(migrated_pg, *OWNER)
    execute(owner, "CREATE TABLE ten01_probe (id uuid PRIMARY KEY, name text)")
    execute(owner, "CREATE INDEX ten01_probe_name_idx ON ten01_probe (name)")
    try:
        problems = tenancy_violations(superuser_url(migrated_pg))
    finally:
        execute(owner, "DROP TABLE ten01_probe")
    assert "ten01_probe: RLS must be enabled and forced" in problems
    assert "ten01_probe: has no RLS policy" in problems
    assert "ten01_probe: needs organisation_id uuid NOT NULL" in problems
    assert (
        "ten01_probe: indexes must lead with organisation_id: ['ten01_probe_name_idx']" in problems
    )
    assert "ten01_probe: needs an index leading with organisation_id" in problems


def test_TEN_01_only_reviewed_definer_functions_exist(migrated_pg: PostgresContainer) -> None:
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT p.proname, p.proconfig, pg_get_userbyid(p.proowner) FROM pg_proc p "
        "JOIN pg_namespace n ON n.oid = p.pronamespace "
        "WHERE p.prosecdef AND n.nspname NOT IN ('pg_catalog', 'information_schema')",
    )
    assert {r[0] for r in rows} == EXPECTED_DEFINER_FUNCTIONS
    for name, config, owner in rows:
        assert owner == "cartlyf_owner", name
        assert config and any(c.startswith("search_path=") for c in config), name


def test_TEN_01_definer_functions_only_executable_by_app(migrated_pg: PostgresContainer) -> None:
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT has_function_privilege('public', 'auth.user_id_by_email(text)', 'EXECUTE'),"
        " has_function_privilege('cartlyf_app', 'auth.user_id_by_email(text)', 'EXECUTE')",
    )
    assert tuple(rows[0]) == (False, True)


def test_TEN_01_app_role_cannot_set_platform_admin_or_rewrite_audit(
    migrated_pg: PostgresContainer,
) -> None:
    rows = fetch(
        superuser_url(migrated_pg),
        "SELECT has_column_privilege('cartlyf_app', 'app_user', 'is_platform_admin', 'UPDATE'),"
        " has_column_privilege('cartlyf_app', 'app_user', 'is_platform_admin', 'INSERT'),"
        " has_table_privilege('cartlyf_app', 'audit_log', 'UPDATE'),"
        " has_table_privilege('cartlyf_app', 'audit_log', 'DELETE')",
    )
    assert tuple(rows[0]) == (False, False, False, False)
