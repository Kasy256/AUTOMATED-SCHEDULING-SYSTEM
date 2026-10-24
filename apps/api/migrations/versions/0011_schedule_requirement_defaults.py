"""schedule: requirement_defaults, the starting hard/weight for new requirements

Revision ID: 0011
Revises: 0010
"""

from alembic import op

revision = "0011"
down_revision = "0010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("ALTER TABLE schedule ADD COLUMN requirement_defaults jsonb")


def downgrade() -> None:
    op.execute("ALTER TABLE schedule DROP COLUMN requirement_defaults")
