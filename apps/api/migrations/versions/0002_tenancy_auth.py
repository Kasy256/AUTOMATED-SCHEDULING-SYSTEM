"""tenancy and auth: identity, organisations, memberships, roles, audit, RLS

Revision ID: 0002
Revises: 0001
"""

from alembic import op

revision = "0002"
down_revision = "0001"
branch_labels = None
depends_on = None

_CONTEXT_FUNCTIONS = [
    "CREATE SCHEMA auth",
    "REVOKE ALL ON SCHEMA auth FROM PUBLIC",
    "GRANT USAGE ON SCHEMA auth TO cartlyf_app",
    """CREATE FUNCTION auth.org_id() RETURNS uuid LANGUAGE sql STABLE
       AS $$ SELECT nullif(current_setting('app.current_org', true), '')::uuid $$""",
    """CREATE FUNCTION auth.user_id() RETURNS uuid LANGUAGE sql STABLE
       AS $$ SELECT nullif(current_setting('app.current_user', true), '')::uuid $$""",
]

_TABLES = [
    """CREATE TABLE organisation (
      id uuid PRIMARY KEY,
      name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
      timezone text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      deleted_at timestamptz
    )""",
    """CREATE TABLE app_user (
      id uuid PRIMARY KEY,
      email citext NOT NULL UNIQUE,
      name text NOT NULL CHECK (char_length(name) BETWEEN 1 AND 200),
      password_hash text,
      email_verified boolean NOT NULL DEFAULT false,
      is_platform_admin boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now(),
      deleted_at timestamptz
    )""",
    """CREATE TABLE membership (
      id uuid PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      user_id uuid NOT NULL REFERENCES app_user (id),
      status text NOT NULL CHECK (status IN ('invited', 'active')),
      created_at timestamptz NOT NULL DEFAULT now(),
      deleted_at timestamptz,
      CONSTRAINT membership_org_user_key UNIQUE (organisation_id, user_id),
      CONSTRAINT membership_org_id_key UNIQUE (organisation_id, id)
    )""",
    """CREATE TABLE membership_role (
      organisation_id uuid NOT NULL,
      membership_id uuid NOT NULL,
      role text NOT NULL CHECK (role IN ('org_admin', 'planner', 'member', 'viewer')),
      PRIMARY KEY (organisation_id, membership_id, role),
      FOREIGN KEY (organisation_id, membership_id)
        REFERENCES membership (organisation_id, id) ON DELETE CASCADE
    )""",
    """CREATE TABLE audit_log (
      id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
      organisation_id uuid NOT NULL REFERENCES organisation (id),
      actor_user_id uuid REFERENCES app_user (id),
      action text NOT NULL,
      target_type text,
      target_id uuid,
      details jsonb NOT NULL DEFAULT '{}',
      via_platform_admin boolean NOT NULL DEFAULT false,
      created_at timestamptz NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX audit_log_org_created_idx ON audit_log (organisation_id, created_at)",
    """CREATE TABLE refresh_token (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES app_user (id),
      family_id uuid NOT NULL,
      token_hash bytea NOT NULL UNIQUE,
      active_organisation_id uuid REFERENCES organisation (id),
      expires_at timestamptz NOT NULL,
      used_at timestamptz,
      revoked_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    )""",
    "CREATE INDEX refresh_token_user_family_idx ON refresh_token (user_id, family_id)",
    """CREATE TABLE email_outbox (
      id uuid PRIMARY KEY,
      user_id uuid NOT NULL REFERENCES app_user (id),
      to_address citext NOT NULL,
      subject text NOT NULL,
      body text NOT NULL,
      attempts integer NOT NULL DEFAULT 0,
      last_error text,
      sent_at timestamptz,
      created_at timestamptz NOT NULL DEFAULT now()
    )""",
]

_ALL_TABLES = [
    "organisation",
    "app_user",
    "membership",
    "membership_role",
    "audit_log",
    "refresh_token",
    "email_outbox",
]

_POLICIES = [
    """CREATE POLICY tenant_isolation ON membership
       USING (organisation_id = (SELECT auth.org_id()))
       WITH CHECK (organisation_id = (SELECT auth.org_id()))""",
    # Lets a user list the organisations they belong to (login, org switch).
    """CREATE POLICY membership_self_read ON membership FOR SELECT
       USING (user_id = (SELECT auth.user_id()))""",
    """CREATE POLICY tenant_isolation ON membership_role
       USING (organisation_id = (SELECT auth.org_id()))
       WITH CHECK (organisation_id = (SELECT auth.org_id()))""",
    """CREATE POLICY tenant_isolation ON audit_log
       USING (organisation_id = (SELECT auth.org_id()))
       WITH CHECK (organisation_id = (SELECT auth.org_id()))""",
    """CREATE POLICY organisation_current ON organisation
       USING (id = (SELECT auth.org_id()))
       WITH CHECK (id = (SELECT auth.org_id()))""",
    """CREATE POLICY organisation_member_read ON organisation FOR SELECT
       USING (EXISTS (
         SELECT 1 FROM membership m
         WHERE m.organisation_id = organisation.id
           AND m.user_id = (SELECT auth.user_id()) AND m.status = 'active'))""",
    """CREATE POLICY app_user_self ON app_user
       USING (id = (SELECT auth.user_id()))
       WITH CHECK (id = (SELECT auth.user_id()))""",
    """CREATE POLICY app_user_org_read ON app_user FOR SELECT
       USING (EXISTS (
         SELECT 1 FROM membership m
         WHERE m.user_id = app_user.id AND m.organisation_id = (SELECT auth.org_id())))""",
    # Sign-up and invitations create identities for someone other than the caller; no read-back.
    "CREATE POLICY app_user_create ON app_user FOR INSERT WITH CHECK (true)",
    "CREATE POLICY app_user_definer_lookup ON app_user FOR SELECT TO cartlyf_owner USING (true)",
    """CREATE POLICY refresh_token_owner ON refresh_token
       USING (user_id = (SELECT auth.user_id()))
       WITH CHECK (user_id = (SELECT auth.user_id()))""",
    """CREATE POLICY refresh_token_definer_lookup ON refresh_token FOR SELECT TO cartlyf_owner
       USING (true)""",
    """CREATE POLICY email_outbox_recipient ON email_outbox
       USING (user_id = (SELECT auth.user_id()))
       WITH CHECK (user_id = (SELECT auth.user_id()))""",
    "CREATE POLICY email_outbox_enqueue ON email_outbox FOR INSERT WITH CHECK (true)",
]

_GRANTS = [
    "REVOKE UPDATE, DELETE ON audit_log FROM cartlyf_app",
    "REVOKE INSERT, UPDATE, DELETE ON app_user FROM cartlyf_app",
    "GRANT INSERT (id, email, name, password_hash, email_verified) ON app_user TO cartlyf_app",
    "GRANT UPDATE (name, password_hash, email_verified) ON app_user TO cartlyf_app",
]

# The only RLS-bypassing code: pre-auth lookups that return an id, never a row.
# search_path keeps public after pg_catalog so citext's = operator still resolves.
_DEFINER_LOOKUPS = [
    """CREATE FUNCTION auth.user_id_by_email(p_email text) RETURNS uuid
       LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
       AS $$ SELECT id FROM public.app_user
             WHERE email = p_email::public.citext AND deleted_at IS NULL $$""",
    """CREATE FUNCTION auth.refresh_token_user_id(p_token_hash bytea) RETURNS uuid
       LANGUAGE sql STABLE SECURITY DEFINER SET search_path = pg_catalog, public
       AS $$ SELECT user_id FROM public.refresh_token WHERE token_hash = p_token_hash $$""",
    "REVOKE EXECUTE ON ALL FUNCTIONS IN SCHEMA auth FROM PUBLIC",
    "GRANT EXECUTE ON ALL FUNCTIONS IN SCHEMA auth TO cartlyf_app",
]


def upgrade() -> None:
    rls = [
        f"ALTER TABLE {table} {action} ROW LEVEL SECURITY"
        for table in _ALL_TABLES
        for action in ("ENABLE", "FORCE")
    ]
    for statement in [*_CONTEXT_FUNCTIONS, *_TABLES, *rls, *_POLICIES, *_GRANTS, *_DEFINER_LOOKUPS]:
        op.execute(statement)


def downgrade() -> None:
    op.execute(f"DROP TABLE {', '.join(reversed(_ALL_TABLES))}")
    op.execute("DROP SCHEMA auth CASCADE")
