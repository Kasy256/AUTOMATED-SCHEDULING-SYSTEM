# Cartlyf

Cartlyf builds schedules automatically: university timetables, hospital rosters, any plan that puts
people, rooms and equipment on a calendar. It works from an organisation's own resources and rules,
and checks every schedule against those rules before anyone sees it.

One configurable product serves every organisation. A customer's policies ("at most 2 sessions a
day", "11 hours' rest between shifts") are configuration, never code.

> **Status:** v1 is feature-complete and in acceptance (Phase 09). Every automated acceptance test
> passes; staging deployment, the restore drill and the load test are pending.

## How it works

```mermaid
flowchart LR
    R[Your resources<br/>people, rooms, groups<br/>skills, sizes, calendars] --> S
    D[What is needed<br/>courses or shifts<br/>become activities to place] --> S
    U[Your rules<br/>picked from a catalogue<br/>hard or soft] --> S
    S[Solver<br/>best plan within<br/>a time limit] --> C[Independent check<br/>re-checks every rule<br/>rejects any breach]
    C --> P[Planner review<br/>drag, pin, ask why<br/>score per rule]
    P --> B[Publish<br/>emails, calendars<br/>CSV, print view]
    B -. something changes:<br/>repair with the fewest changes .-> S
    style C stroke-width:3px
```

The solver proposes a plan, and a separate checker must confirm it breaks no hard rule before a
planner ever sees it. After publishing, any change goes back through a repair that keeps the rest
of the plan.

## The building blocks

| Idea | What it means | University example | Hospital example |
| --- | --- | --- | --- |
| **Resources** | The people, places, equipment and groups that get booked, with tags (skills), a size or capacity, and an availability calendar | Lecturers tagged with their subjects; rooms with seat counts; student groups with headcounts | Nurses tagged RN, midwife or ICU, with contracted hours |
| **Demands** | What needs scheduling; each demand becomes activities to place | "Data Structures: 2 sessions of 2 hours a week for BIT1 and BCS1" | "Every day, Ward A needs 3 RNs and 1 midwife on the Day shift" |
| **Rules** | Limits and preferences from a catalogue, set as *hard* (must hold) or *soft* (avoid, with a weight) | At most 2 sessions a day per lecturer; rooms must seat the whole class | At least 11 hours' rest between shifts; at most 3 nights in a row |
| **Schedule** | One planning problem: a date range, a time zone, its demands and rules | "Term 1 2026" | "Ward A + B, January 2027" |
| **Versions** | Each solve makes a draft; publishing locks it; edits make a new draft | Draft 3 published as the term timetable | A sick-call repair published as version 2 |

Industry templates (**Education** and **Healthcare** in v1) set up resource types, time slots and a
default rule set in one click; every value stays editable.

## Features

| Feature | What it does |
| --- | --- |
| **Automatic solving** | Google OR-Tools CP-SAT searches for the best plan that obeys every hard rule, in the background, with a time limit, live progress and cancel |
| **Independent checker** | A separate program re-checks every result; nothing that breaks a hard rule is saved, shown or published |
| **Score breakdown** | Shows what each soft rule cost in the final plan |
| **No-code rule builder** | 14 rule templates filled in with forms: who it applies to, the limit, hard or soft |
| **Planner board** | People-by-time grid with drag-and-drop, live green/red validation with the reason, pins, keyboard support |
| **Explanations** | "Why is this here?", "Why can't it go there?", and "Why is this impossible?" with the rules to relax |
| **Minimal-change repair** | Re-plans after a sick call or closure, freezes the past, and shows a diff before publishing |
| **Fairness ledger** | Balances nights and weekends across people, counting previous rosters |
| **Versions and publishing** | Draft, published, archived; a diff between any two versions |
| **Notifications and calendars** | Emails people a published change (with automatic re-sending if delivery fails); personal iCal feeds |
| **Exports and reports** | CSV, print view; utilisation, load per person, coverage gaps, fairness spread |
| **CSV import** | Column mapping, a dry run listing every bad row, all-or-nothing import, pre-solve feasibility check |
| **Roles** | Org admin, planner, member, viewer; one person can hold several |

### Rule catalogue

Always on: no double-booking, nobody scheduled while unavailable, every slot filled with someone
qualified, pins respected.

| Rule | In plain words |
| --- | --- |
| Room fits the class (`capacity_fit`) | The room seats everyone assigned to it |
| Maximum load (`max_load`) | At most so many sessions or hours per day, week or schedule, optionally within a time window |
| Minimum load (`min_load`) | At least so many hours, such as contracted hours |
| Minimum rest (`min_rest`) | A minimum gap between someone's consecutive assignments |
| Maximum in a row (`max_consecutive`) | Limits consecutive days, or consecutive shifts of a kind such as nights |
| Spread (`spread`) | Sessions of the same course spread out, e.g. never twice a day |
| Same time (`same_time`) | Linked activities start together |
| Order (`precedence`) | One activity ends before another starts, with a gap |
| Preferences (`preference`) | Reward preferred times, avoid disliked ones, per person |
| Fewer gaps (`minimize_gaps`) | Avoid idle hours between someone's sessions in a day |
| Balance (`balance`) | Share the workload evenly |
| Fairness over time (`fairness`) | Share nights and weekends evenly, counting history |
| Even weekdays (`day_distribution`) | Spread a group's sessions across the week |
| Stability (`stability`) | Penalise changes to the published plan (used by repair) |

## Trust and data

- **Tenant isolation.** Organisations share the platform, not their data. PostgreSQL row-level
  security (enabled and forced) refuses one organisation's rows to another, even if application
  code had a bug. The app connects as a non-superuser role without `BYPASSRLS`, and an isolation
  test tries every endpoint across two organisations on every push.
- **Verified schedules.** Solver and checker are separate implementations of each rule; if they
  disagree, the result is discarded and an alert is raised.
- **Accounts.** argon2id password hashes, rate-limited sign-in, 15-minute access tokens with
  rotating refresh tokens.
- **Hosting (v1).** Render in Frankfurt (API, worker, Postgres 16 with daily backups and
  point-in-time recovery, Key Value) and Cloudflare Pages for the web app. Errors go to Sentry
  with personal data stripped.

## Repository layout

```
apps/api/         FastAPI app + Dramatiq worker (package cartlyf_api), Alembic migrations, DB roles
apps/web/         React 18 + TypeScript + Vite SPA (Tailwind, shadcn/ui, TanStack Query, orval client)
packages/engine/  Pure scheduling engine (package cartlyf_engine): no DB, network, clock or env access
tools/            Smoke test, Render deploy helper, demo seeding, load test, ISBAT benchmark report
render.yaml       Render blueprint (staging and production)
```

The Education template is benchmarked against the university's former timetabling system: its data
lives as versioned fixtures in `packages/engine/tests/fixtures/isbat/`.

## Getting started (run it on your computer)

Cartlyf runs entirely on your machine: no accounts, keys or hosting needed. The database, queue and
file storage run in Docker; the API, the solve worker and the web app run from three terminals.
Allow about 20 minutes the first time.

### 1. Install the tools (once)

| Tool | Why | Install | Check |
|---|---|---|---|
| **Git** | Clone the repo | [git-scm.com](https://git-scm.com/downloads) | `git --version` |
| **Docker Desktop** | Runs Postgres 16, Redis and MinIO (file storage) | [docker.com](https://www.docker.com/products/docker-desktop/) | `docker info` (Docker Desktop must be running) |
| **uv** | Installs Python 3.12 and the backend packages | [docs.astral.sh/uv](https://docs.astral.sh/uv/getting-started/installation/) | `uv --version` |
| **Node.js 24** | Builds and serves the web app | [nodejs.org](https://nodejs.org/) (or `nvm use`, see `.nvmrc`) | `node --version` |
| **pnpm** | Web app packages | `corepack enable` (ships with Node) | `pnpm --version` |

### 2. Get the code and set it up (once)

```sh
git clone https://github.com/Kasy256/AUTOMATED-SCHEDULING-SYSTEM.git cartlyf
cd cartlyf
git checkout Development        # the latest code; main is the released version
cp .env.example .env            # Windows PowerShell: Copy-Item .env.example .env
docker compose up -d --wait postgres redis minio   # starts the database, queue and file storage
docker compose up minio-init    # creates the storage bucket, then exits
uv sync                         # installs Python 3.12 and the backend
uv run --env-file .env alembic -c apps/api/alembic.ini upgrade head   # creates the database tables
cd apps/web && pnpm install && pnpm api:generate && cd ../..
```

The values in `.env.example` are throwaway local passwords and are fine as they are. If ports 5432,
6379 or 9000 are already used on your machine, change `CARTLYF_POSTGRES_PORT`, `CARTLYF_REDIS_PORT`
or `CARTLYF_MINIO_PORT` in `.env` (and the same port in the URLs that use it) before
`docker compose up`.

### 3. Start the system

Open three terminals in the repo folder and run one command in each; leave them running.

```sh
# 1. API (http://localhost:8000)
uv run --env-file .env uvicorn cartlyf_api.main:create_app --factory --reload

# 2. Solve worker (runs the scheduling engine in the background)
uv run --env-file .env dramatiq cartlyf_api.jobs.worker

# 3. Web app (http://localhost:5173)
cd apps/web && pnpm dev
```

Open **http://localhost:5173**.

### 4. Log in

**Option A: load the demo organisations** (recommended for a first look). In a fourth terminal:

```sh
uv run --env-file .env python tools/seed_demo.py ../cartlyf-demo-accounts.json
```

It builds, through the product itself, the ISBAT university term (lecturers, rooms, groups,
courses) and a 4-week, 40-nurse hospital roster, which takes a few minutes. The emails and
passwords it creates are saved in `cartlyf-demo-accounts.json`, next to (not inside) the repo
folder. Log in with those, open a schedule and press **Solve**.

**Option B: sign up yourself.** Emails are not sent locally; they are printed in the **API
terminal** instead. Sign up in the web app, then find the line containing `email_console` in the API
terminal and open the `http://localhost:5173/confirm-email?token=...` link from it.

### 5. Stop and start again

- Stop: press `Ctrl+C` in the three terminals, then `docker compose stop`. Your data is kept.
- Start again: `docker compose up -d --wait postgres redis minio`, then step 3. After pulling new code, also re-run
  `uv sync`, the `alembic ... upgrade head` command and, in `apps/web`, `pnpm install && pnpm api:generate`.
- Start from scratch (deletes all local data): `docker compose down -v`, then step 2 from the first
  `docker compose up`.

### Troubleshooting

| Problem | Fix |
|---|---|
| `docker compose` fails or hangs | Start Docker Desktop and wait until it says it is running. |
| "port is already allocated" | Another program uses that port: change it in `.env` (step 2). |
| Database login fails after editing passwords in `.env` | The database keeps the passwords from its first start: `docker compose down -v` and set up again. |
| The web app loads but every action fails | The API terminal is not running, or shows an error. `http://localhost:8000/api/v1/health` should answer `"status":"ok"`. |
| A solve stays "queued" | The worker terminal is not running. |
| Changed API and the web app shows type errors | Run `pnpm api:generate` in `apps/web`. |

`GET /api/v1/health` also reports the database role the API connected as. It returns 503 if that role
is a superuser or has `BYPASSRLS`, because row-level security is the tenant boundary. See
`apps/api/db/README.md` for the two database roles.

## Checks

```sh
uv run ruff check . && uv run ruff format --check . && uv run pyright && uv run lint-imports
uv run pytest                     # integration tests start Postgres/Redis/MinIO with Testcontainers

cd apps/web
pnpm lint && pnpm format:check && pnpm typecheck && pnpm test && pnpm build
pnpm e2e                          # Playwright; needs the worker running
```

CI (`.github/workflows/ci.yml`) runs the same checks plus gitleaks, `pip-audit` and `pnpm audit`,
then deploys `Development` to staging and `main` to production (after a reviewer approves).

## Not in v1

Staff self-service (availability entry, shift swaps), SMS/WhatsApp, two-way calendar sync, a native
mobile app, further industry templates, forecasting and payroll links, SSO, public API keys and
billing are on the roadmap, not built.
