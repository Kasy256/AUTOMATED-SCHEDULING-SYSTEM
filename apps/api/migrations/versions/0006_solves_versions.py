"""solve runs, solution versions, assignments and calendar feeds

Revision ID: 0006
Revises: 0005
"""

from alembic import op

revision = "0006"
down_revision = "0005"
branch_labels = None
depends_on = None


def _org_fk(columns: str, table: str, referenced: str = "organisation_id, id") -> str:
    return f"FOREIGN KEY (organisation_id, {columns}) REFERENCES {table} ({referenced})"


_RUN_STATUSES = (
    "'queued','running','succeeded','infeasible','no_solution',"
    "'cancelled','failed','failed_verification'"
)

_TABLES = [
    "ALTER TABLE resource ADD COLUMN user_id uuid REFERENCES app_user (id)",
    """CREATE UNIQUE INDEX resource_org_user_live_idx ON resource (organisation_id, user_id)
       WHERE user_id IS NOT NULL AND deleted_at IS NULL""",
    f"""CREATE TABLE solve_run (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      requested_by uuid NOT NULL REFERENCES app_user (id),
      status text NOT NULL CHECK (status IN ({_RUN_STATUSES})),
      problem jsonb NOT NULL,
      problem_hash text NOT NULL,
      horizon_origin timestamptz NOT NULL,
      timezone text NOT NULL,
      progress jsonb NOT NULL DEFAULT '{{}}',
      conflicts text[] NOT NULL DEFAULT '{{}}',
      error text,
      version_id uuid,
      cancel_requested_at timestamptz,
      heartbeat_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now(),
      started_at timestamptz,
      finished_at timestamptz,
      CONSTRAINT solve_run_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("schedule_id", "schedule")}
    )""",
    """CREATE INDEX solve_run_org_schedule_idx
       ON solve_run (organisation_id, schedule_id, created_at DESC)""",
    """CREATE INDEX solve_run_org_active_idx ON solve_run (organisation_id)
       WHERE status IN ('queued', 'running')""",
    f"""CREATE TABLE solution_version (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      solve_run_id uuid NOT NULL,
      parent_version_id uuid,
      number integer NOT NULL CHECK (number > 0),
      status text NOT NULL CHECK (status IN ('draft', 'published', 'archived')),
      solver_status text NOT NULL,
      score jsonb NOT NULL,
      checker_report jsonb NOT NULL,
      created_by uuid NOT NULL REFERENCES app_user (id),
      created_at timestamptz NOT NULL DEFAULT now(),
      published_at timestamptz,
      published_by uuid REFERENCES app_user (id),
      archived_at timestamptz,
      CONSTRAINT solution_version_org_id_key UNIQUE (organisation_id, id),
      CONSTRAINT solution_version_org_schedule_number_key
        UNIQUE (organisation_id, schedule_id, number),
      {_org_fk("schedule_id", "schedule")},
      {_org_fk("solve_run_id", "solve_run")},
      {_org_fk("parent_version_id", "solution_version")}
    )""",
    """CREATE UNIQUE INDEX solution_version_one_published_idx
       ON solution_version (organisation_id, schedule_id) WHERE status = 'published'""",
    "CREATE INDEX solution_version_org_run_idx ON solution_version (organisation_id, solve_run_id)",
    """CREATE INDEX solution_version_org_parent_idx
       ON solution_version (organisation_id, parent_version_id)""",
    # Activities can be regenerated away, so a version snapshot carries no FK to them.
    f"""CREATE TABLE assignment (
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      version_id uuid NOT NULL,
      activity_id uuid NOT NULL,
      start_at timestamptz NOT NULL,
      end_at timestamptz NOT NULL,
      PRIMARY KEY (organisation_id, version_id, activity_id),
      {_org_fk("version_id", "solution_version")} ON DELETE CASCADE
    )""",
    f"""CREATE TABLE assignment_resource (
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      version_id uuid NOT NULL,
      activity_id uuid NOT NULL,
      role text NOT NULL,
      resource_id uuid NOT NULL,
      PRIMARY KEY (organisation_id, version_id, activity_id, role, resource_id),
      {_org_fk("version_id, activity_id", "assignment", "organisation_id, version_id, activity_id")}
        ON DELETE CASCADE
    )""",
    """CREATE INDEX assignment_resource_org_resource_idx
       ON assignment_resource (organisation_id, resource_id, version_id)""",
    f"""CREATE TABLE calendar_feed (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      resource_id uuid NOT NULL,
      token_hash bytea NOT NULL UNIQUE,
      created_by uuid NOT NULL REFERENCES app_user (id),
      created_at timestamptz NOT NULL DEFAULT now(),
      revoked_at timestamptz,
      CONSTRAINT calendar_feed_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("resource_id", "resource")}
    )""",
    "CREATE INDEX calendar_feed_org_resource_idx ON calendar_feed (organisation_id, resource_id)",
]

_TENANT_TABLES = [
    "solve_run",
    "solution_version",
    "assignment",
    "assignment_resource",
    "calendar_feed",
]

_GUARDS = [
    "REVOKE UPDATE, DELETE ON assignment, assignment_resource FROM cartlyf_app",
    # The run's problem snapshot anchors its versions, so only lifecycle columns may change.
    "REVOKE UPDATE, DELETE ON solve_run FROM cartlyf_app",
    "GRANT UPDATE (status, progress, conflicts, error, version_id, cancel_requested_at, "
    "heartbeat_at, started_at, finished_at) ON solve_run TO cartlyf_app",
    "REVOKE UPDATE, DELETE ON solution_version FROM cartlyf_app",
    "GRANT UPDATE (status, published_at, published_by, archived_at) "
    "ON solution_version TO cartlyf_app",
    """CREATE FUNCTION solution_version_transition() RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN
         IF NEW.status <> OLD.status AND NOT (
              (OLD.status = 'draft' AND NEW.status IN ('published', 'archived'))
              OR (OLD.status = 'published' AND NEW.status = 'archived')) THEN
           RAISE EXCEPTION 'invalid version transition % -> %', OLD.status, NEW.status;
         END IF;
         RETURN NEW;
       END $$""",
    """CREATE TRIGGER solution_version_transition BEFORE UPDATE ON solution_version
       FOR EACH ROW EXECUTE FUNCTION solution_version_transition()""",
    # Runs as the invoking user, so RLS applies and the version is visible in the same org.
    """CREATE FUNCTION assignment_requires_draft() RETURNS trigger LANGUAGE plpgsql AS $$
       BEGIN
         IF NOT EXISTS (SELECT 1 FROM solution_version
                        WHERE organisation_id = NEW.organisation_id AND id = NEW.version_id
                          AND status = 'draft') THEN
           RAISE EXCEPTION 'assignments can only be added to a draft version';
         END IF;
         RETURN NEW;
       END $$""",
    """CREATE TRIGGER assignment_requires_draft BEFORE INSERT ON assignment
       FOR EACH ROW EXECUTE FUNCTION assignment_requires_draft()""",
    """CREATE TRIGGER assignment_resource_requires_draft BEFORE INSERT ON assignment_resource
       FOR EACH ROW EXECUTE FUNCTION assignment_requires_draft()""",
    # Pre-auth lookup for capability URLs: returns an org id, never a row (same rule as 0002).
    """CREATE FUNCTION auth.calendar_feed_org(p_token_hash bytea) RETURNS uuid
       LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
       AS $$ SELECT organisation_id FROM public.calendar_feed
             WHERE token_hash = p_token_hash AND revoked_at IS NULL $$""",
    "CREATE POLICY calendar_feed_definer_lookup ON calendar_feed FOR SELECT TO cartlyf_owner "
    "USING (true)",
    "REVOKE EXECUTE ON FUNCTION auth.calendar_feed_org(bytea) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION auth.calendar_feed_org(bytea) TO cartlyf_app",
]


def upgrade() -> None:
    for statement in _TABLES:
        op.execute(statement)
    for table in _TENANT_TABLES:
        op.execute(f"ALTER TABLE {table} ENABLE ROW LEVEL SECURITY")
        op.execute(f"ALTER TABLE {table} FORCE ROW LEVEL SECURITY")
        op.execute(
            f"""CREATE POLICY tenant_isolation ON {table}
                USING (organisation_id = (SELECT auth.org_id()))
                WITH CHECK (organisation_id = (SELECT auth.org_id()))"""
        )
    for statement in _GUARDS:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP FUNCTION auth.calendar_feed_org(bytea)")
    op.execute(f"DROP TABLE {', '.join(reversed(_TENANT_TABLES))}")
    op.execute("DROP FUNCTION solution_version_transition()")
    op.execute("DROP FUNCTION assignment_requires_draft()")
    op.execute("DROP INDEX resource_org_user_live_idx")
    op.execute("ALTER TABLE resource DROP COLUMN user_id")
