# Database roles

Cartlyf uses two Postgres roles in the `cartlyf` database:

| Role | Used by | Privileges |
|---|---|---|
| `cartlyf_owner` | Alembic migrations only | Owns the database and the `public` schema; creates tables, policies, extensions. |
| `cartlyf_app` | API and worker | `LOGIN NOSUPERUSER NOBYPASSRLS NOINHERIT`; `USAGE` on `public` plus DML on tables the owner creates (default privileges from the baseline migration). Cannot run DDL. |

The app role must never be a superuser or have `BYPASSRLS`: row-level security is the tenant
boundary, and either attribute silently disables it. `GET /api/v1/health` returns 503 if it does.

## Creating the roles

`roles.sql` runs once per cluster, as a superuser, through `psql` (it uses psql variables and
`\connect`):

```sh
psql -U postgres -d postgres \
  -v owner_password='...' -v app_password='...' \
  -f apps/api/db/roles.sql
```

Locally, `docker compose up` does this automatically: `Dockerfile` bakes `roles.sql` and
`docker-init.sh` into the Postgres image, which runs them on the first start of an empty volume,
using the passwords from `.env`. After editing `roles.sql`, rebuild with `docker compose build`. To re-run it, remove the volume:
`docker compose down -v`.

Managed hosts (e.g. Render) create the database and a non-superuser admin that owns it, so
`roles.sql` does not apply there. Instead, once per environment, run `managed_roles.sql` as that
admin, connected to the `cartlyf` database:

```sh
psql "$ADMIN_URL" -v owner_password='...' -v app_password='...' -f apps/api/db/managed_roles.sql
```

It creates the same two roles, gives the owner `CREATE` on the database (for the trusted
`citext`/`btree_gist` extensions) and ownership of `public`. The admin is not used by the app.

## Migrations

Alembic connects as `cartlyf_owner` using `CARTLYF_MIGRATION_DATABASE_URL`:

```sh
uv run --env-file .env alembic -c apps/api/alembic.ini upgrade head
```
