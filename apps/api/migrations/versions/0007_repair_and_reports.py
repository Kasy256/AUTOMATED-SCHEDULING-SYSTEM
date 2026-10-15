"""solve runs: repair kind, baseline, freeze instant, infeasibility report

Revision ID: 0007
Revises: 0006
"""

from alembic import op

revision = "0007"
down_revision = "0006"
branch_labels = None
depends_on = None

_UP = [
    "ALTER TABLE solve_run ADD COLUMN kind text NOT NULL DEFAULT 'solve' "
    "CHECK (kind IN ('solve', 'repair'))",
    "ALTER TABLE solve_run ADD COLUMN baseline_version_id uuid",
    "ALTER TABLE solve_run ADD COLUMN freeze_before timestamptz",
    "ALTER TABLE solve_run ADD COLUMN infeasibility jsonb",
    """ALTER TABLE solve_run ADD CONSTRAINT solve_run_baseline_fk
       FOREIGN KEY (organisation_id, baseline_version_id)
       REFERENCES solution_version (organisation_id, id)""",
    """ALTER TABLE solve_run ADD CONSTRAINT solve_run_repair_ck
       CHECK ((kind = 'repair')
              = (baseline_version_id IS NOT NULL AND freeze_before IS NOT NULL))""",
    "GRANT UPDATE (infeasibility) ON solve_run TO cartlyf_app",
]
_DOWN = [
    "REVOKE UPDATE (infeasibility) ON solve_run FROM cartlyf_app",
    "ALTER TABLE solve_run DROP CONSTRAINT solve_run_repair_ck",
    "ALTER TABLE solve_run DROP CONSTRAINT solve_run_baseline_fk",
    "ALTER TABLE solve_run DROP COLUMN infeasibility",
    "ALTER TABLE solve_run DROP COLUMN freeze_before",
    "ALTER TABLE solve_run DROP COLUMN baseline_version_id",
    "ALTER TABLE solve_run DROP COLUMN kind",
]


def upgrade() -> None:
    for statement in _UP:
        op.execute(statement)


def downgrade() -> None:
    for statement in _DOWN:
        op.execute(statement)
