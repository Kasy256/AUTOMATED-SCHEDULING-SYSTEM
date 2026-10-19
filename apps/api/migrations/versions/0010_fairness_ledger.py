"""fairness_ledger: per-person counted work of published versions, by local day

Revision ID: 0010
Revises: 0009
"""

from alembic import op

revision = "0010"
down_revision = "0009"
branch_labels = None
depends_on = None

_UP = [
    """CREATE TABLE fairness_ledger (
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      schedule_id uuid NOT NULL,
      version_id uuid NOT NULL,
      resource_id uuid NOT NULL,
      counter text NOT NULL,
      day date NOT NULL,
      count integer NOT NULL CHECK (count > 0),
      PRIMARY KEY (organisation_id, schedule_id, resource_id, counter, day),
      FOREIGN KEY (organisation_id, schedule_id) REFERENCES schedule (organisation_id, id),
      FOREIGN KEY (organisation_id, version_id) REFERENCES solution_version (organisation_id, id),
      FOREIGN KEY (organisation_id, resource_id) REFERENCES resource (organisation_id, id)
    )""",
    """CREATE INDEX fairness_ledger_org_counter_day_idx
       ON fairness_ledger (organisation_id, counter, day)""",
    "ALTER TABLE fairness_ledger ENABLE ROW LEVEL SECURITY",
    "ALTER TABLE fairness_ledger FORCE ROW LEVEL SECURITY",
    """CREATE POLICY tenant_isolation ON fairness_ledger
       USING (organisation_id = (SELECT auth.org_id()))
       WITH CHECK (organisation_id = (SELECT auth.org_id()))""",
    # Rows are replaced wholesale on publish, never edited.
    "REVOKE ALL ON fairness_ledger FROM cartlyf_app",
    "GRANT SELECT, INSERT, DELETE ON fairness_ledger TO cartlyf_app",
]


def upgrade() -> None:
    for statement in _UP:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP TABLE fairness_ledger")
