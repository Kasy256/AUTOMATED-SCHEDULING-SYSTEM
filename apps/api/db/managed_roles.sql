-- Managed Postgres (e.g. Render): the host creates the `cartlyf` database and a non-superuser
-- admin that owns it. Run once per environment, as that admin, connected to `cartlyf`:
--   psql "$ADMIN_URL" -v owner_password='...' -v app_password='...' -f managed_roles.sql
\set ON_ERROR_STOP on

CREATE ROLE cartlyf_owner LOGIN PASSWORD :'owner_password'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION;
CREATE ROLE cartlyf_app LOGIN PASSWORD :'app_password'
  NOSUPERUSER NOBYPASSRLS NOCREATEDB NOCREATEROLE NOREPLICATION NOINHERIT;

-- ALTER ... OWNER needs SET on the new owner; no INHERIT, so the admin keeps its own rights only.
GRANT cartlyf_owner TO CURRENT_USER WITH INHERIT FALSE, SET TRUE;

REVOKE ALL ON DATABASE cartlyf FROM PUBLIC;
-- CREATE lets the owner install the trusted extensions (citext, btree_gist) the baseline needs.
GRANT CONNECT, CREATE ON DATABASE cartlyf TO cartlyf_owner;
GRANT CONNECT ON DATABASE cartlyf TO cartlyf_app;

ALTER SCHEMA public OWNER TO cartlyf_owner;
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO cartlyf_app;
