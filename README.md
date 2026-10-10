# Cartlyf

Cartlyf is a multi-tenant scheduling platform: one configurable product that any organisation
(a university, a hospital, a service team) sets up with its own resources, demands and rules.
Rules are configuration, not code; a pure CP-SAT engine solves the schedule, and an independent
checker verifies every solution before anyone sees it.

> Status: Phase 00 scaffold. The engine, API and web app are empty skeletons, wired together
> and tested.

## Repository layout

```
apps/api/        FastAPI app + Dramatiq worker (package cartlyf_api), Alembic migrations, DB roles
apps/web/        React 18 + TypeScript + Vite SPA (Tailwind, shadcn/ui, TanStack Query, orval client)
packages/engine/ Pure scheduling engine (package cartlyf_engine): no DB, network, clock or env access
ISBAT-TIMETABLE-BACKEND/   Legacy ISBAT timetabler: read-only reference and benchmark data
ISBAT-TIMETABLE-FRONTEND/  Legacy ISBAT frontend: read-only reference
```

The legacy folders are kept for reference and as the Education benchmark. Do not edit them.

## Prerequisites

- [uv](https://docs.astral.sh/uv/) (manages Python 3.12 and the workspace)
- Node.js 24 (see `.nvmrc`) and [pnpm](https://pnpm.io/)
- Docker (for Postgres 16, Redis 7 and MinIO locally, and for the test suite)

## Run locally

```sh
cp .env.example .env          # then change the passwords; change the ports if 5432/6379 are taken
docker compose up -d --wait   # Postgres 16 (cartlyf_owner / cartlyf_app roles), Redis 7, MinIO (S3 API) + bucket
uv sync
uv run --env-file .env alembic -c apps/api/alembic.ini upgrade head
```

API and worker (separate terminals):

```sh
uv run --env-file .env uvicorn cartlyf_api.main:create_app --factory --reload
uv run --env-file .env dramatiq cartlyf_api.jobs.worker
```

Web app (proxies `/api` to the API on port 8000):

```sh
cd apps/web
pnpm install
pnpm api:generate   # exports the OpenAPI schema from the API and generates the typed client
pnpm dev
```

`GET /api/v1/health` reports the database role the API connected as. It returns 503 if that role is
a superuser or has `BYPASSRLS`, because row-level security is the tenant boundary. See
`apps/api/db/README.md` for the two database roles.

## Checks

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports
uv run pytest                     # integration tests start Postgres/Redis with Testcontainers

cd apps/web
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test && pnpm build
```

CI (`.github/workflows/ci.yml`) runs the same checks, plus gitleaks, `pip-audit` and `pnpm audit`.
