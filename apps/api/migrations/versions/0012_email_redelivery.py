"""email_outbox: definer lookup of unsent emails for the re-delivery sweep

Revision ID: 0012
Revises: 0011
"""

from alembic import op

revision = "0012"
down_revision = "0011"
branch_labels = None
depends_on = None

# Same rule as the 0002 lookups: ids, never rows. The sweep then reads and sends each email
# under its recipient's own RLS context, exactly like a first delivery.
_UPGRADE = [
    """CREATE FUNCTION auth.pending_emails(p_max_attempts integer, p_limit integer)
       RETURNS TABLE (outbox_id uuid, user_id uuid)
       LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
       AS $$ SELECT id, user_id FROM public.email_outbox
             WHERE sent_at IS NULL AND attempts < p_max_attempts
             ORDER BY created_at LIMIT p_limit $$""",
    "CREATE POLICY email_outbox_definer_lookup ON email_outbox FOR SELECT TO cartlyf_owner "
    "USING (true)",
    "REVOKE EXECUTE ON FUNCTION auth.pending_emails(integer, integer) FROM PUBLIC",
    "GRANT EXECUTE ON FUNCTION auth.pending_emails(integer, integer) TO cartlyf_app",
]


def upgrade() -> None:
    for statement in _UPGRADE:
        op.execute(statement)


def downgrade() -> None:
    op.execute("DROP POLICY email_outbox_definer_lookup ON email_outbox")
    op.execute("DROP FUNCTION auth.pending_emails(integer, integer)")
