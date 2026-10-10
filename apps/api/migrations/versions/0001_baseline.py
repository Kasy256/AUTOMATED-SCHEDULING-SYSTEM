"""baseline: extensions and default privileges for the app role

Revision ID: 0001
Revises:
"""

from alembic import op

revision = "0001"
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS citext")
    op.execute("CREATE EXTENSION IF NOT EXISTS btree_gist")
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE cartlyf_owner IN SCHEMA public "
        "GRANT SELECT, INSERT, UPDATE, DELETE ON TABLES TO cartlyf_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE cartlyf_owner IN SCHEMA public "
        "GRANT USAGE, SELECT ON SEQUENCES TO cartlyf_app"
    )


def downgrade() -> None:
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE cartlyf_owner IN SCHEMA public "
        "REVOKE USAGE, SELECT ON SEQUENCES FROM cartlyf_app"
    )
    op.execute(
        "ALTER DEFAULT PRIVILEGES FOR ROLE cartlyf_owner IN SCHEMA public "
        "REVOKE SELECT, INSERT, UPDATE, DELETE ON TABLES FROM cartlyf_app"
    )
    op.execute("DROP EXTENSION IF EXISTS btree_gist")
    op.execute("DROP EXTENSION IF EXISTS citext")
