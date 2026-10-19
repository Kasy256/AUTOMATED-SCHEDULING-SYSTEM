"""industry_template: seed the Healthcare rostering template (v1)

Revision ID: 0009
Revises: 0008
"""

import json
from pathlib import Path

import sqlalchemy as sa
from alembic import op

revision = "0009"
down_revision = "0008"
branch_labels = None
depends_on = None

# Frozen copy (normalised definition) of data/healthcare.json.
_SEED = Path(__file__).with_name("0009_healthcare_v1.json")


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
    op.execute("DELETE FROM industry_template WHERE key = 'healthcare' AND version = 1")
    op.execute("DROP POLICY industry_template_unseed ON industry_template")
