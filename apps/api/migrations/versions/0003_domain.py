"""domain configuration: resources, calendars, schedules, demands, activities, rules, imports

Revision ID: 0003
Revises: 0002
"""

from alembic import op

revision = "0003"
down_revision = "0002"
branch_labels = None
depends_on = None

_KEY = r"CHECK ({col} ~ '^[a-z][a-z0-9_]{{0,62}}$')"
_NAME = "CHECK (char_length(name) BETWEEN 1 AND 200)"
_STAMPS = """created_at timestamptz NOT NULL DEFAULT now(),
      updated_at timestamptz NOT NULL DEFAULT now()"""
_KIND_OF_AVAILABILITY = "CHECK (kind IN ('available', 'unavailable', 'preferred', 'avoided'))"


def _org_fk(column: str, table: str, on_delete: str = "") -> str:
    return (
        f"FOREIGN KEY (organisation_id, {column}) REFERENCES {table} (organisation_id, id)"
        f"{' ON DELETE ' + on_delete if on_delete else ''}"
    )


_TABLES = [
    f"""CREATE TABLE resource_type (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      key text NOT NULL {_KEY.format(col="key")},
      name text NOT NULL {_NAME},
      kind text NOT NULL CHECK (kind IN ('person', 'space', 'asset', 'group')),
      attribute_schema jsonb NOT NULL,
      {_STAMPS},
      deleted_at timestamptz,
      CONSTRAINT resource_type_org_id_key UNIQUE (organisation_id, id)
    )""",
    """CREATE UNIQUE INDEX resource_type_org_key_live_idx ON resource_type (organisation_id, key)
       WHERE deleted_at IS NULL""",
    f"""CREATE TABLE resource (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      resource_type_id uuid NOT NULL,
      code text NOT NULL CHECK (char_length(code) BETWEEN 1 AND 100),
      name text NOT NULL {_NAME},
      tags text[] NOT NULL DEFAULT '{{}}',
      attributes jsonb NOT NULL DEFAULT '{{}}',
      capacity integer CHECK (capacity > 0),
      size integer CHECK (size > 0),
      concurrency integer NOT NULL DEFAULT 1 CHECK (concurrency > 0),
      {_STAMPS},
      deleted_at timestamptz,
      CONSTRAINT resource_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("resource_type_id", "resource_type")}
    )""",
    """CREATE UNIQUE INDEX resource_org_code_live_idx ON resource (organisation_id, code)
       WHERE deleted_at IS NULL""",
    "CREATE INDEX resource_org_type_idx ON resource (organisation_id, resource_type_id)",
    f"""CREATE TABLE availability_rule (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      resource_id uuid NOT NULL,
      kind text NOT NULL {_KIND_OF_AVAILABILITY},
      weekday smallint NOT NULL CHECK (weekday BETWEEN 0 AND 6),
      start_minute smallint NOT NULL CHECK (start_minute BETWEEN 0 AND 1439),
      end_minute smallint NOT NULL CHECK (end_minute BETWEEN 1 AND 1440),
      created_at timestamptz NOT NULL DEFAULT now(),
      CHECK (end_minute > start_minute),
      {_org_fk("resource_id", "resource", "CASCADE")}
    )""",
    """CREATE INDEX availability_rule_org_resource_idx
       ON availability_rule (organisation_id, resource_id)""",
    f"""CREATE TABLE availability_exception (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      resource_id uuid NOT NULL,
      kind text NOT NULL {_KIND_OF_AVAILABILITY},
      starts_at timestamptz NOT NULL,
      ends_at timestamptz NOT NULL,
      reason text CHECK (char_length(reason) <= 500),
      created_at timestamptz NOT NULL DEFAULT now(),
      CHECK (ends_at > starts_at),
      {_org_fk("resource_id", "resource", "CASCADE")}
    )""",
    """CREATE INDEX availability_exception_org_resource_idx
       ON availability_exception (organisation_id, resource_id)""",
    f"""CREATE TABLE schedule (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      name text NOT NULL {_NAME},
      timezone text NOT NULL,
      start_date date NOT NULL,
      end_date date NOT NULL,
      day_parts jsonb NOT NULL,
      {_STAMPS},
      deleted_at timestamptz,
      CHECK (end_date >= start_date),
      CONSTRAINT schedule_org_id_key UNIQUE (organisation_id, id)
    )""",
    f"""CREATE TABLE slot_template (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      name text NOT NULL {_NAME},
      definition jsonb NOT NULL,
      {_STAMPS},
      CONSTRAINT slot_template_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("schedule_id", "schedule")}
    )""",
    "CREATE INDEX slot_template_org_schedule_idx ON slot_template (organisation_id, schedule_id)",
    f"""CREATE TABLE demand (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      slot_template_id uuid NOT NULL,
      name text NOT NULL {_NAME},
      kind text NOT NULL CHECK (kind IN ('session', 'coverage')),
      spec jsonb NOT NULL,
      {_STAMPS},
      deleted_at timestamptz,
      CONSTRAINT demand_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("schedule_id", "schedule")},
      {_org_fk("slot_template_id", "slot_template")}
    )""",
    "CREATE INDEX demand_org_schedule_idx ON demand (organisation_id, schedule_id)",
    "CREATE INDEX demand_org_slot_template_idx ON demand (organisation_id, slot_template_id)",
    f"""CREATE TABLE activity (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      demand_id uuid,
      series_id uuid,
      name text NOT NULL {_NAME},
      duration_minutes integer NOT NULL CHECK (duration_minutes > 0),
      candidate_starts timestamptz[] NOT NULL CHECK (cardinality(candidate_starts) > 0),
      attrs jsonb NOT NULL DEFAULT '{{}}',
      created_at timestamptz NOT NULL DEFAULT now(),
      CONSTRAINT activity_org_id_key UNIQUE (organisation_id, id),
      {_org_fk("schedule_id", "schedule")},
      {_org_fk("demand_id", "demand", "CASCADE")}
    )""",
    "CREATE INDEX activity_org_schedule_idx ON activity (organisation_id, schedule_id)",
    "CREATE INDEX activity_org_demand_idx ON activity (organisation_id, demand_id)",
    f"""CREATE TABLE requirement (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      activity_id uuid NOT NULL,
      position smallint NOT NULL,
      role text NOT NULL {_KEY.format(col="role")},
      resource_type_id uuid,
      tags text[] NOT NULL DEFAULT '{{}}',
      attr_predicates jsonb NOT NULL DEFAULT '[]',
      count_min integer NOT NULL CHECK (count_min >= 0),
      count_max integer NOT NULL CHECK (count_max >= 1),
      fixed_resource_ids uuid[] NOT NULL DEFAULT '{{}}',
      hard boolean NOT NULL DEFAULT true,
      weight integer NOT NULL DEFAULT 0 CHECK (weight >= 0),
      CHECK (count_max >= count_min),
      CONSTRAINT requirement_org_activity_role_key UNIQUE (organisation_id, activity_id, role),
      {_org_fk("activity_id", "activity", "CASCADE")},
      {_org_fk("resource_type_id", "resource_type")}
    )""",
    "CREATE INDEX requirement_org_type_idx ON requirement (organisation_id, resource_type_id)",
    f"""CREATE TABLE constraint_instance (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      name text NOT NULL {_NAME},
      template_key text NOT NULL,
      template_version integer NOT NULL CHECK (template_version > 0),
      params jsonb NOT NULL,
      scope jsonb NOT NULL,
      hard boolean NOT NULL,
      weight integer NOT NULL DEFAULT 0 CHECK (weight >= 0),
      enabled boolean NOT NULL DEFAULT true,
      {_STAMPS},
      deleted_at timestamptz,
      {_org_fk("schedule_id", "schedule")}
    )""",
    """CREATE INDEX constraint_instance_org_schedule_idx
       ON constraint_instance (organisation_id, schedule_id)""",
    f"""CREATE TABLE pin (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      activity_id uuid NOT NULL,
      start_at timestamptz,
      resources jsonb NOT NULL DEFAULT '{{}}',
      {_STAMPS},
      CHECK (start_at IS NOT NULL OR resources <> '{{}}'::jsonb),
      CONSTRAINT pin_org_activity_key UNIQUE (organisation_id, activity_id),
      {_org_fk("schedule_id", "schedule")},
      {_org_fk("activity_id", "activity", "CASCADE")}
    )""",
    "CREATE INDEX pin_org_schedule_idx ON pin (organisation_id, schedule_id)",
    f"""CREATE TABLE import_job (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      kind text NOT NULL CHECK (kind IN ('resources', 'demands')),
      status text NOT NULL
        CHECK (status IN ('awaiting_file', 'uploaded', 'validated', 'invalid', 'committed')),
      resource_type_id uuid,
      schedule_id uuid,
      filename text NOT NULL CHECK (char_length(filename) BETWEEN 1 AND 200),
      object_key text,
      size_bytes integer,
      content_sha256 text,
      columns jsonb,
      mapping jsonb,
      report jsonb,
      created_by uuid NOT NULL REFERENCES app_user (id),
      {_STAMPS},
      committed_at timestamptz,
      CHECK ((kind = 'resources') = (resource_type_id IS NOT NULL)),
      CHECK ((kind = 'demands') = (schedule_id IS NOT NULL)),
      {_org_fk("resource_type_id", "resource_type")},
      {_org_fk("schedule_id", "schedule")}
    )""",
    "CREATE INDEX import_job_org_created_idx ON import_job (organisation_id, created_at)",
    "CREATE INDEX import_job_org_type_idx ON import_job (organisation_id, resource_type_id)",
    "CREATE INDEX import_job_org_schedule_idx ON import_job (organisation_id, schedule_id)",
]

_TENANT_TABLES = [
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


def downgrade() -> None:
    op.execute(f"DROP TABLE {', '.join(reversed(_TENANT_TABLES))}")
