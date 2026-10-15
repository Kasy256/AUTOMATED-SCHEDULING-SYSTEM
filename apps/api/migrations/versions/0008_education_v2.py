"""industry_template: Education v2 adds a stability rule so repairs work out of the box

Revision ID: 0008
Revises: 0007
"""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0008"
down_revision = "0007"
branch_labels = None
depends_on = None

# Frozen copy (normalised definition); v1 stays as seeded by 0005.
_SEED = Path(__file__).with_name("0008_education_v2.json")


def upgrade() -> None:
    definition = json.loads(_SEED.read_text(encoding="utf-8"))
    op.get_bind().execute(
        sa.text(
            "INSERT INTO industry_template (key, version, name, definition) "
            "VALUES (:key, :version, :name, CAST(:definition AS jsonb))"
        ),
        {
            "key": definition["key"],
            "version": definition["version"],
            "name": definition["name"],
            "definition": json.dumps(definition),
        },
    )


def downgrade() -> None:
    # FORCE binds the owner too; a delete policy exists only for the length of this step.
    op.execute(
        "CREATE POLICY industry_template_unseed ON industry_template FOR DELETE "
        "TO cartlyf_owner USING (true)"
    )
    op.execute("DELETE FROM industry_template WHERE key = 'education' AND version = 2")
    op.execute("DROP POLICY industry_template_unseed ON industry_template")
