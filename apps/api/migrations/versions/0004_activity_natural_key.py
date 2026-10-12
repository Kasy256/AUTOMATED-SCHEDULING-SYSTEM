"""activity natural key: generated activities keep their id across demand regenerations

Revision ID: 0004
Revises: 0003
"""

from alembic import op

revision = "0004"
down_revision = "0003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Nullable: manual activities have no key, and rows created before this get one on their
    # next regeneration.
    op.execute("ALTER TABLE activity ADD COLUMN natural_key text")
    op.execute(
        """CREATE UNIQUE INDEX activity_org_demand_key_idx
           ON activity (organisation_id, demand_id, natural_key)
           WHERE demand_id IS NOT NULL AND natural_key IS NOT NULL"""
    )


def downgrade() -> None:
    op.execute("DROP INDEX activity_org_demand_key_idx")
    op.execute("ALTER TABLE activity DROP COLUMN natural_key")
