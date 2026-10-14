from uuid import uuid4

import pytest
from sqlalchemy.exc import DBAPIError, IntegrityError, ProgrammingError
from testcontainers.community.postgres import PostgresContainer

from support import APP, db_url, execute, execute_many, fetch, seed_org, superuser_url

pytestmark = pytest.mark.integration


def _seed_version(
    url: str, org: str, status: str = "draft", number: int = 1, schedule: str | None = None
) -> tuple[str, str]:
    """Insert (as superuser) a run and version, plus a schedule unless one is given."""
    new_schedule, run, version, activity, resource = (str(uuid4()) for _ in range(5))
    schedule = schedule or new_schedule
    user = fetch(url, f"SELECT user_id FROM membership WHERE organisation_id = '{org}'")[0][0]
    execute_many(
        url,
        [
            *(
                []
                if schedule != new_schedule
                else [
                    "INSERT INTO schedule (id, organisation_id, name, timezone, start_date, "
                    f"end_date, day_parts) VALUES ('{schedule}', '{org}', 'S', 'Africa/Kampala', "
                    """'2027-01-11', '2027-01-15', '{"version": 1, "parts": []}')"""
                ]
            ),
            "INSERT INTO solve_run (id, organisation_id, schedule_id, requested_by, status, "
            "problem, problem_hash, horizon_origin, timezone) "
            f"VALUES ('{run}', '{org}', '{schedule}', '{user}', 'succeeded', '{{}}', 'h', now(), "
            "'Africa/Kampala')",
            "INSERT INTO solution_version (id, organisation_id, schedule_id, solve_run_id, number, "
            "status, solver_status, score, checker_report, created_by) "
            f"VALUES ('{version}', '{org}', '{schedule}', '{run}', {number}, 'draft', "
            f"'optimal', '{{}}', '{{}}', '{user}')",
            "INSERT INTO assignment (organisation_id, version_id, activity_id, start_at, end_at) "
            f"VALUES ('{org}', '{version}', '{activity}', now(), now() + interval '1 hour')",
            "INSERT INTO assignment_resource (organisation_id, version_id, activity_id, role, "
            f"resource_id) VALUES ('{org}', '{version}', '{activity}', 'room', '{resource}')",
            f"UPDATE solution_version SET status = '{status}' WHERE id = '{version}'",
        ],
    )
    return schedule, version


def _as_app(org: str, *statements: str) -> list[str]:
    return [f"SELECT set_config('app.current_org', '{org}', true)", *statements]


def test_published_version_columns_are_immutable(migrated_pg: PostgresContainer) -> None:
    url, app = superuser_url(migrated_pg), db_url(migrated_pg, *APP)
    org = str(seed_org(url, "Solve Immutable").organisation_id)
    _, version = _seed_version(url, org)
    where = f"WHERE id = '{version}'"

    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, f"UPDATE solution_version SET score = '{{}}' {where}"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, "UPDATE assignment SET end_at = now()"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, "DELETE FROM assignment"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, "UPDATE assignment_resource SET role = 'x'"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, "DELETE FROM assignment_resource"))

    execute_many(
        app,
        _as_app(
            org,
            f"UPDATE solution_version SET status = 'published', published_at = now() {where}",
        ),
    )
    with pytest.raises(DBAPIError, match="invalid version transition"):
        execute_many(app, _as_app(org, f"UPDATE solution_version SET status = 'draft' {where}"))
    execute_many(
        app,
        _as_app(
            org, f"UPDATE solution_version SET status = 'archived', archived_at = now() {where}"
        ),
    )
    with pytest.raises(DBAPIError, match="invalid version transition"):
        execute_many(app, _as_app(org, f"UPDATE solution_version SET status = 'published' {where}"))


def test_one_published_version_per_schedule(migrated_pg: PostgresContainer) -> None:
    url = superuser_url(migrated_pg)
    org = str(seed_org(url, "Solve One Published").organisation_id)
    schedule, _ = _seed_version(url, org, status="published")
    run = fetch(url, f"SELECT id FROM solve_run WHERE schedule_id = '{schedule}'")[0][0]
    user = fetch(url, f"SELECT user_id FROM membership WHERE organisation_id = '{org}'")[0][0]
    insert = (
        "INSERT INTO solution_version (id, organisation_id, schedule_id, solve_run_id, number, "
        "status, solver_status, score, checker_report, created_by) "
        f"VALUES ('{{id}}', '{org}', '{schedule}', '{run}', {{number}}, '{{status}}', 'optimal', "
        f"'{{{{}}}}', '{{{{}}}}', '{user}')"
    )
    execute(url, insert.format(id=uuid4(), number=2, status="draft"))
    with pytest.raises(IntegrityError, match="solution_version_one_published_idx"):
        execute(url, insert.format(id=uuid4(), number=3, status="published"))


def test_calendar_feed_org_lookup_ignores_revoked(migrated_pg: PostgresContainer) -> None:
    url, app = superuser_url(migrated_pg), db_url(migrated_pg, *APP)
    seeded = seed_org(url, "Solve Feed")
    org, user = seeded.organisation_id, seeded.user_id
    resource = fetch(url, f"SELECT id FROM resource WHERE organisation_id = '{org}'")[0][0]
    token_hash = uuid4().hex
    execute(
        url,
        "INSERT INTO calendar_feed (id, organisation_id, resource_id, token_hash, created_by) "
        f"VALUES ('{uuid4()}', '{org}', '{resource}', decode('{token_hash}', 'hex'), '{user}')",
    )
    lookup = "SELECT auth.calendar_feed_org(decode('{}', 'hex'))"
    assert fetch(app, lookup.format(token_hash))[0][0] == org
    assert fetch(app, lookup.format(uuid4().hex))[0][0] is None
    execute(url, f"UPDATE calendar_feed SET revoked_at = now() WHERE organisation_id = '{org}'")
    assert fetch(app, lookup.format(token_hash))[0][0] is None


def test_versions_are_never_deleted_and_assignments_only_join_drafts(
    migrated_pg: PostgresContainer,
) -> None:
    url, app = superuser_url(migrated_pg), db_url(migrated_pg, *APP)
    org = str(seed_org(url, "Solve Draft Only").organisation_id)
    schedule, draft = _seed_version(url, org)
    _, published = _seed_version(url, org, status="published", number=2, schedule=schedule)
    insert_assignment = (
        "INSERT INTO assignment (organisation_id, version_id, activity_id, start_at, end_at) "
        f"VALUES ('{org}', '{{}}', '{uuid4()}', now(), now() + interval '1 hour')"
    )
    insert_resource = (
        "INSERT INTO assignment_resource (organisation_id, version_id, activity_id, role, "
        f"resource_id) VALUES ('{org}', '{{}}', '{uuid4()}', 'room', '{uuid4()}')"
    )

    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, f"DELETE FROM solution_version WHERE id = '{draft}'"))
    for insert in (insert_assignment, insert_resource):
        with pytest.raises(DBAPIError, match="only be added to a draft version"):
            execute_many(app, _as_app(org, insert.format(published)))
    execute_many(app, _as_app(org, insert_assignment.format(draft)))

    execute_many(
        app,
        _as_app(
            org,
            f"UPDATE solution_version SET status = 'archived', archived_at = now() "
            f"WHERE id = '{draft}'",
        ),
    )
    with pytest.raises(DBAPIError, match="only be added to a draft version"):
        execute_many(app, _as_app(org, insert_assignment.format(draft)))


def test_solve_run_snapshot_is_immutable(migrated_pg: PostgresContainer) -> None:
    url, app = superuser_url(migrated_pg), db_url(migrated_pg, *APP)
    org = str(seed_org(url, "Solve Run Immutable").organisation_id)
    schedule, _ = _seed_version(url, org)
    where = f"WHERE schedule_id = '{schedule}'"

    for column, value in (
        ("problem", "'{}'"),
        ("problem_hash", "'x'"),
        ("horizon_origin", "now()"),
        ("timezone", "'UTC'"),
    ):
        with pytest.raises(ProgrammingError, match="permission denied"):
            execute_many(app, _as_app(org, f"UPDATE solve_run SET {column} = {value} {where}"))
    with pytest.raises(ProgrammingError, match="permission denied"):
        execute_many(app, _as_app(org, f"DELETE FROM solve_run {where}"))

    execute_many(
        app,
        _as_app(
            org,
            "UPDATE solve_run SET status = 'failed', progress = '{}', conflicts = '{}', "
            "error = 'e', version_id = NULL, cancel_requested_at = now(), heartbeat_at = now(), "
            f"started_at = now(), finished_at = now() {where}",
        ),
    )
