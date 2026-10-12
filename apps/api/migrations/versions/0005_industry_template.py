"""industry_template: global, read-only starter configurations (seeded with Education v1)

Revision ID: 0005
Revises: 0004
"""

import json

import sqlalchemy as sa
from alembic import op

from cartlyf_api.industry_templates.schemas import load_packaged

revision = "0005"
down_revision = "0004"
branch_labels = None
depends_on = None

_SEEDED = ["education"]


def upgrade() -> None:
    op.execute(
        """CREATE TABLE industry_template (
               key text NOT NULL,
               version integer NOT NULL,
               name text NOT NULL,
               definition jsonb NOT NULL,
               created_at timestamptz NOT NULL DEFAULT now(),
               PRIMARY KEY (key, version)
           )"""
    )
    op.execute("ALTER TABLE industry_template ENABLE ROW LEVEL SECURITY")
    op.execute("ALTER TABLE industry_template FORCE ROW LEVEL SECURITY")
    # Global reference data: every tenant may read it, nobody but the owner may change it.
    op.execute("CREATE POLICY industry_template_read ON industry_template FOR SELECT USING (true)")
    op.execute("REVOKE INSERT, UPDATE, DELETE, TRUNCATE ON industry_template FROM cartlyf_app")
    insert = sa.text(
        "INSERT INTO industry_template (key, version, name, definition) "
        "VALUES (:key, :version, :name, CAST(:definition AS jsonb))"
    )
    # FORCE binds the owner too, so seeding (now and in later migrations) needs its own policy.
    op.execute(
        "CREATE POLICY industry_template_seed ON industry_template FOR INSERT TO cartlyf_owner "
        "WITH CHECK (true)"
    )
    for key in _SEEDED:
        template = load_packaged(key)
        op.get_bind().execute(
            insert,
            {
                "key": template.key,
                "version": template.version,
                "name": template.name,
                "definition": json.dumps(template.model_dump(mode="json")),
            },
        )


def downgrade() -> None:
    op.execute("DROP TABLE industry_template")
