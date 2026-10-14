import asyncio
import importlib
import json
import re
import sys
from collections.abc import Generator, Iterable, Mapping
from contextlib import contextmanager
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4
from zoneinfo import ZoneInfo

import dramatiq
import httpx2 as httpx
import pytest
import redis
from alembic.config import Config
from dramatiq import Broker, Worker
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sentry_sdk.envelope import Envelope
from sentry_sdk.transport import Transport
from sentry_sdk.types import Event
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from cartlyf_api.db import create_db_engine
from cartlyf_api.email.provider import ConsoleEmailProvider
from cartlyf_api.examples import EXAMPLE_IDS
from cartlyf_api.jobs.broker import SOLVE_QUEUE, setup_broker
from cartlyf_api.settings import Settings
from cartlyf_api.solves.runner import SolveFn, execute_run
from cartlyf_engine.solve import solve

API_DIR = Path(__file__).resolve().parents[1]
OWNER = ("cartlyf_owner", "owner-test-password")
APP = ("cartlyf_app", "app-test-password")
TEST_JWT_SECRET = "test-secret-" + "x" * 40


def make_settings(database_url: str, redis_url: str, **overrides: object) -> Settings:
    return Settings.model_validate(
        {
            "database_url": database_url,
            "redis_url": redis_url,
            "jwt_secret": TEST_JWT_SECRET,
            "web_base_url": "http://web.test",
            "public_api_base_url": "http://api.test",
            "cookie_secure": False,
            "s3_endpoint": "127.0.0.1:1",
            "s3_access_key": "test-access-key",
            "s3_secret_key": "test-secret-key",
            "s3_bucket": "cartlyf-test",
            "s3_secure": False,
            **overrides,
        }
    )


def apply_roles(pg: PostgresContainer) -> None:
    # Piped over exec rather than bind-mounted: some Docker hosts cannot see every host drive.
    sql = (API_DIR / "db" / "roles.sql").read_text(encoding="utf-8")
    script = (
        'printf "%s" "$1" | psql -U "$2" -d postgres '
        '-v owner_password="$3" -v app_password="$4" -f -'
    )
    code, output = pg.exec(["sh", "-c", script, "sh", sql, pg.username, OWNER[1], APP[1]])
    assert code == 0, repr(output)


def db_url(pg: PostgresContainer, user: str, password: str, dbname: str = "cartlyf") -> str:
    host, port = pg.get_container_host_ip(), pg.get_exposed_port(5432)
    return f"postgresql+asyncpg://{user}:{password}@{host}:{port}/{dbname}"


def alembic_config(url: str) -> Config:
    config = Config(str(API_DIR / "alembic.ini"))
    config.attributes["database_url"] = url
    return config


# Any: raw SQL rows are untyped; tests assert on their values.
def fetch(url: str, sql: str) -> list[tuple[Any, ...]]:
    async def run() -> list[tuple[Any, ...]]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                return [tuple(row) for row in (await conn.execute(text(sql))).all()]
        finally:
            await engine.dispose()

    return asyncio.run(run())


def execute(url: str, sql: str) -> None:
    async def run() -> None:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                await conn.execute(text(sql))
        finally:
            await engine.dispose()

    asyncio.run(run())


def execute_many(url: str, statements: list[str]) -> None:
    async def run() -> None:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                for statement in statements:
                    await conn.execute(text(statement))
        finally:
            await engine.dispose()

    asyncio.run(run())


def superuser_url(pg: PostgresContainer) -> str:
    return db_url(pg, pg.username, pg.password)


@dataclass(frozen=True)
class SeededOrg:
    organisation_id: UUID
    user_id: UUID
    membership_id: UUID


def seed_org(url: str, name: str) -> SeededOrg:
    """Insert (as superuser) an org with an org_admin member and a row in every auth table."""
    org, user, membership = uuid4(), uuid4(), uuid4()
    email = f"{user.hex}@example.com"
    statements = [
        "INSERT INTO organisation (id, name, timezone) "
        f"VALUES ('{org}', '{name}', 'Africa/Kampala')",
        "INSERT INTO app_user (id, email, name, email_verified) "
        f"VALUES ('{user}', '{email}', 'Seed User', true)",
        "INSERT INTO membership (id, organisation_id, user_id, status) "
        f"VALUES ('{membership}', '{org}', '{user}', 'active')",
        "INSERT INTO membership_role (organisation_id, membership_id, role) "
        f"VALUES ('{org}', '{membership}', 'org_admin')",
        "INSERT INTO audit_log (organisation_id, actor_user_id, action) "
        f"VALUES ('{org}', '{user}', 'seed')",
        "INSERT INTO refresh_token (id, user_id, family_id, token_hash, expires_at) "
        f"VALUES ('{uuid4()}', '{user}', '{uuid4()}', '\\x{uuid4().hex}', "
        "now() + interval '1 day')",
        "INSERT INTO email_outbox (id, user_id, to_address, subject, body) "
        f"VALUES ('{uuid4()}', '{user}', '{email}', 's', 'b')",
    ]
    rt, res, sched, slot, dem, act = (uuid4() for _ in range(6))
    empty_schema = '{"version": 1, "attributes": []}'
    statements += [
        "INSERT INTO resource_type (id, organisation_id, key, name, kind, attribute_schema) "
        f"VALUES ('{rt}', '{org}', 'seed_type', 'Seed', 'space', '{empty_schema}')",
        "INSERT INTO resource (id, organisation_id, resource_type_id, code, name) "
        f"VALUES ('{res}', '{org}', '{rt}', 'SEED-1', 'Seed resource')",
        "INSERT INTO availability_rule (id, organisation_id, resource_id, kind, weekday, "
        f"start_minute, end_minute) VALUES ('{uuid4()}', '{org}', '{res}', 'available', 0, 480, "
        "1020)",
        "INSERT INTO availability_exception (id, organisation_id, resource_id, kind, starts_at, "
        f"ends_at) VALUES ('{uuid4()}', '{org}', '{res}', 'unavailable', now(), "
        "now() + interval '1 day')",
        "INSERT INTO schedule (id, organisation_id, name, timezone, start_date, end_date, "
        f"day_parts) VALUES ('{sched}', '{org}', 'Seed', 'Africa/Kampala', '2027-01-11', "
        """'2027-01-15', '{"version": 1, "parts": []}')""",
        "INSERT INTO slot_template (id, organisation_id, schedule_id, name, definition) "
        f"""VALUES ('{slot}', '{org}', '{sched}', 'Seed', '{{"version": 1, "slots": []}}')""",
        "INSERT INTO demand (id, organisation_id, schedule_id, slot_template_id, name, kind, spec) "
        f"VALUES ('{dem}', '{org}', '{sched}', '{slot}', 'Seed', 'session', '{{}}')",
        "INSERT INTO activity (id, organisation_id, schedule_id, demand_id, series_id, name, "
        f"duration_minutes, candidate_starts) VALUES ('{act}', '{org}', '{sched}', '{dem}', "
        f"'{dem}', 'Seed', 60, ARRAY[now()])",
        "INSERT INTO requirement (id, organisation_id, activity_id, position, role, count_min, "
        f"count_max) VALUES ('{uuid4()}', '{org}', '{act}', 0, 'room', 1, 1)",
        "INSERT INTO constraint_instance (id, organisation_id, schedule_id, name, template_key, "
        f"template_version, params, scope, hard) VALUES ('{uuid4()}', '{org}', '{sched}', "
        """'Seed', 'min_rest', 1, '{"minutes": 60}', '{}', true)""",
        "INSERT INTO pin (id, organisation_id, schedule_id, activity_id, start_at) "
        f"VALUES ('{uuid4()}', '{org}', '{sched}', '{act}', now())",
        "INSERT INTO import_job (id, organisation_id, kind, status, resource_type_id, filename, "
        f"created_by) VALUES ('{uuid4()}', '{org}', 'resources', 'awaiting_file', '{rt}', "
        f"'seed.csv', '{user}')",
    ]
    execute_many(url, statements)
    return SeededOrg(org, user, membership)


DEFAULT_PASSWORD = "correct horse battery"


def signup_body(
    email: str,
    password: str,
    org_name: str = "Test Org",
    timezone: str = "Africa/Kampala",
) -> dict[str, str]:
    return {
        "email": email,
        "name": "Test User",
        "password": password,
        "organisation_name": org_name,
        "timezone": timezone,
    }


def signup(
    client: TestClient,
    email: str | None = None,
    password: str = DEFAULT_PASSWORD,
    org_name: str = "Test Org",
    timezone: str = "Africa/Kampala",
) -> str:
    email = email or f"{uuid4().hex}@example.com"
    response = client.post(
        "/api/v1/auth/signup", json=signup_body(email, password, org_name, timezone)
    )
    assert response.status_code == 202, response.text
    return email


def sent_emails(app: FastAPI) -> ConsoleEmailProvider:
    provider = app.state.email_provider
    assert isinstance(provider, ConsoleEmailProvider)
    return provider


def latest_link_token(app: FastAPI, to: str, path: str) -> str:
    for message in reversed(sent_emails(app).sent):
        match = re.search(rf"/{path}\?token=([\w.-]+)", message.body)
        if message.to == to and match:
            return match.group(1)
    raise AssertionError(f"no {path} email for {to}")


@dataclass(frozen=True)
class Account:
    email: str
    password: str
    access_token: str
    refresh_token: str
    organisation_id: UUID

    @property
    def auth(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.access_token}"}


def add_member(
    client: TestClient,
    app: FastAPI,
    admin: Account,
    roles: list[str],
    email: str | None = None,
) -> Account:
    """Invite a new person into the admin's organisation and accept as them."""
    email = email or f"{uuid4().hex}@example.com"
    invited = client.post(
        "/api/v1/invitations",
        headers=admin.auth,
        json={"email": email, "name": "Invited Person", "roles": roles},
    )
    assert invited.status_code == 201, invited.text
    token = latest_link_token(app, email, "accept-invitation")
    accepted = client.post(
        "/api/v1/auth/accept-invitation", json={"token": token, "password": DEFAULT_PASSWORD}
    )
    assert accepted.status_code == 200, accepted.text
    body = accepted.json()
    return Account(
        email,
        DEFAULT_PASSWORD,
        body["access_token"],
        accepted.cookies[REFRESH_COOKIE],
        UUID(body["organisation_id"]),
    )


@dataclass(frozen=True)
class Operation:
    path: str
    method: str
    path_params: list[str]
    body: object | None


# Any: the OpenAPI document is untyped JSON.
def openapi_operations(app: FastAPI) -> list[Operation]:
    """Every route in the app's OpenAPI schema, with an example body where it takes one."""
    spec: dict[str, Any] = app.openapi()
    operations: list[Operation] = []
    for path, item in spec["paths"].items():
        for method, op in item.items():
            params = [p["name"] for p in op.get("parameters", []) if p["in"] == "path"]
            operations.append(Operation(path, method.upper(), params, _example_body(spec, op)))
    return operations


def _example_body(spec: dict[str, Any], op: dict[str, Any]) -> object | None:
    body = op.get("requestBody")
    if body is None or "application/json" not in body["content"]:
        return None  # raw uploads (e.g. text/csv) carry no ids; the harness sends no body
    name = body["content"]["application/json"]["schema"]["$ref"].rsplit("/", 1)[-1]
    examples = spec["components"]["schemas"][name].get("examples")
    assert examples, f"{name}: add json_schema_extra examples so the isolation harness can call it"
    return examples[0]


_SENTINELS = {str(uuid): name for name, uuid in EXAMPLE_IDS.items()}


def body_id_names(value: object) -> set[str]:
    if isinstance(value, str):
        return {_SENTINELS[value]} if value in _SENTINELS else set()
    if isinstance(value, list):
        return set[str]().union(*(body_id_names(v) for v in cast(list[object], value)))
    if isinstance(value, dict):
        values = cast(dict[str, object], value).values()
        return set[str]().union(*(body_id_names(v) for v in values))
    return set()


def substitute_ids(value: object, ids: Mapping[str, str]) -> object:
    """Replace example placeholder ids with the seeded ids of one organisation."""
    if isinstance(value, str) and value in _SENTINELS:
        name = _SENTINELS[value]
        assert name in ids, f"seed an id for {name!r} in seed_config"
        return ids[name]
    if isinstance(value, list):
        return [substitute_ids(v, ids) for v in cast(list[object], value)]
    if isinstance(value, dict):
        return {k: substitute_ids(v, ids) for k, v in cast(dict[str, object], value).items()}
    return value


def ordered(operations: list[Operation]) -> list[Operation]:
    """Non-DELETE routes first; DELETEs deepest first, children (reverse-alphabetical) before
    parents, so a positive-control delete never removes an object a later route still needs."""
    deletes = [op for op in operations if op.method == "DELETE"]
    others = [op for op in operations if op.method != "DELETE"]
    return others + sorted(deletes, key=lambda op: (op.path.count("/"), op.path), reverse=True)


def url_for(op: Operation, ids: Mapping[str, str]) -> str:
    return op.path.format(**{name: ids[name] for name in op.path_params})


def seed_config(client: TestClient, admin: Account) -> dict[str, str]:
    """Create one of each configuration object in the admin's org; returns ids by path name."""

    def post(path: str, body: object) -> str:
        response = client.post(path, headers=admin.auth, json=body)
        assert response.status_code == 201, f"{path}: {response.text}"
        return response.json()["id"]

    ids: dict[str, str] = {}
    me = client.get("/api/v1/auth/me", headers=admin.auth)
    assert me.status_code == 200, me.text
    ids["user_id"] = me.json()["user_id"]
    ids["resource_type_id"] = post(
        "/api/v1/resource-types",
        {
            "key": "lecturer",
            "name": "Lecturer",
            "kind": "person",
            "attribute_schema": {
                "version": 1,
                "attributes": [
                    {"key": "employment", "type": "enum", "enum_values": ["full_time", "part_time"]}
                ],
            },
        },
    )
    ids["resource_id"] = post(
        "/api/v1/resources",
        {
            "resource_type_id": ids["resource_type_id"],
            "code": "LEC-001",
            "name": "Seed lecturer",
            "tags": ["math101"],
            "attributes": {"employment": "full_time"},
        },
    )
    # A distinct group resource: fixing the lecturer as the demand's group made the seed unsolvable.
    group_type_id = post(
        "/api/v1/resource-types", {"key": "cohort", "name": "Cohort", "kind": "group"}
    )
    ids["group_resource_id"] = post(
        "/api/v1/resources",
        {"resource_type_id": group_type_id, "code": "GRP-001", "name": "Seed cohort"},
    )
    resource_base = f"/api/v1/resources/{ids['resource_id']}"
    ids["availability_rule_id"] = post(
        f"{resource_base}/availability-rules",
        {"kind": "available", "weekday": 0, "start_minute": 480, "end_minute": 1020},
    )
    ids["availability_exception_id"] = post(
        f"{resource_base}/availability-exceptions",
        {
            "kind": "unavailable",
            "starts_at": "2027-01-12T08:00:00+03:00",
            "ends_at": "2027-01-12T10:00:00+03:00",
        },
    )
    ids["schedule_id"] = post(
        "/api/v1/schedules",
        {
            "name": "Seed term",
            "timezone": "Africa/Kampala",
            "start_date": "2027-01-11",
            "end_date": "2027-01-15",
        },
    )
    ids["slot_template_id"] = post(
        f"/api/v1/schedules/{ids['schedule_id']}/slot-templates",
        {
            "name": "Periods",
            "definition": {
                "version": 1,
                "slots": [
                    {
                        "label": "P1",
                        "weekdays": [0, 1, 2, 3, 4],
                        "start_minute": 510,
                        "duration_minutes": 115,
                    },
                    {
                        "label": "P2",
                        "weekdays": [0, 1, 2, 3, 4],
                        "start_minute": 660,
                        "duration_minutes": 115,
                    },
                ],
            },
        },
    )
    schedule_base = f"/api/v1/schedules/{ids['schedule_id']}"
    ids["demand_id"] = post(
        f"{schedule_base}/demands",
        {
            "name": "Seed demand",
            "slot_template_id": ids["slot_template_id"],
            "spec": {
                "kind": "session",
                "sessions_per_week": 1,
                "requirements": [
                    {"role": "lecturer", "resource_type_id": ids["resource_type_id"]},
                    {"role": "group", "fixed_resource_ids": [ids["group_resource_id"]]},
                ],
            },
        },
    )
    ids["activity_id"] = post(
        f"{schedule_base}/activities",
        {
            "name": "Seed meeting",
            "duration_minutes": 60,
            "candidate_starts": ["2027-01-11T09:00:00+03:00", "2027-01-12T09:00:00+03:00"],
            "requirements": [{"role": "lecturer", "resource_type_id": ids["resource_type_id"]}],
        },
    )
    ids["constraint_instance_id"] = post(
        f"/api/v1/schedules/{ids['schedule_id']}/constraints",
        {
            "name": "Seed rule",
            "template_key": "max_load",
            "template_version": 1,
            "params": {"period": "day", "max_count": 2},
            "hard": True,
        },
    )
    ids["import_id"] = post(
        "/api/v1/imports",
        {"kind": "resources", "resource_type_id": ids["resource_type_id"], "filename": "seed.csv"},
    )
    uploaded = client.put(
        f"/api/v1/imports/{ids['import_id']}/file",
        headers=admin.auth | {"Content-Type": "text/csv"},
        content=b"Code,Name\nIMP-SEED,Imported seed\n",
    )
    assert uploaded.status_code == 200, uploaded.text
    ids["run_id"], ids["version_id"] = solve_now(client, admin, ids["schedule_id"])
    _, ids["other_version_id"] = solve_now(client, admin, ids["schedule_id"])
    feed = client.post(f"{resource_base}/calendar-feeds", headers=admin.auth)
    assert feed.status_code == 201, feed.text
    ids["calendar_feed_id"] = feed.json()["id"]
    ids["token"] = feed.json()["url"].rsplit("/", 1)[-1].removesuffix(".ics")
    return ids


def post_accepted(client: TestClient, admin: Account, path: str) -> str:
    response = client.post(path, headers=admin.auth, json={})
    assert response.status_code == 202, f"{path}: {response.text}"
    return response.json()["id"]


def redis_queue_length(app: FastAPI, queue: str) -> int:
    """Messages waiting on a Dramatiq queue (list `<namespace>:<queue>` in Redis)."""
    client = redis.Redis.from_url(str(app.state.settings.redis_url))  # pyright: ignore[reportUnknownMemberType]
    try:
        return client.llen(f"dramatiq:{queue}")  # pyright: ignore[reportReturnType]
    finally:
        client.close()


def missing_seeds(operation: Operation, ids: dict[str, str]) -> set[str]:
    return set(operation.path_params) - ids.keys()


@dataclass(frozen=True)
class World:
    """Two organisations: A with an admin, a viewer and a member; B with an admin."""

    a_admin: Account
    a_viewer: Account
    a_member: Account
    b_admin: Account
    a_ids: dict[str, str]
    b_ids: dict[str, str]


def build_world(client: TestClient, app: FastAPI) -> World:
    a_admin = signup_and_confirm(client, app, org_name="World A")
    b_admin = signup_and_confirm(client, app, org_name="World B")
    a_viewer = add_member(client, app, a_admin, ["viewer"])
    a_member = add_member(client, app, a_admin, ["member"])

    # One id per path-parameter name used by any route; add a seed when a route adds a name.
    def ids(admin: Account) -> dict[str, str]:
        members = client.get("/api/v1/members", headers=admin.auth).json()
        own = next(m for m in members if m["email"] == admin.email)
        return {
            "membership_id": own["membership_id"],
            "organisation_id": str(admin.organisation_id),
            **seed_config(client, admin),
        }

    return World(a_admin, a_viewer, a_member, b_admin, ids(a_admin), ids(b_admin))


def refresh_with(client: TestClient, raw: str) -> httpx.Response:
    client.cookies.clear()
    return client.post("/api/v1/auth/refresh", headers={"Cookie": f"{REFRESH_COOKIE}={raw}"})


def signup_and_confirm(
    client: TestClient,
    app: FastAPI,
    org_name: str = "Test Org",
    password: str = DEFAULT_PASSWORD,
) -> Account:
    email = signup(client, password=password, org_name=org_name)
    token = latest_link_token(app, email, "confirm-email")
    response = client.post("/api/v1/auth/confirm-email", json={"token": token})
    assert response.status_code == 200, response.text
    body = response.json()
    return Account(
        email,
        password,
        body["access_token"],
        response.cookies[REFRESH_COOKIE],
        UUID(body["organisation_id"]),
    )


@dataclass(frozen=True)
class BuiltSchedule:
    schedule_id: str
    lecturer_type_id: str
    lecturer_ids: list[str]
    activities: int


def build_schedule(
    client: TestClient,
    admin: Account,
    *,
    lecturers: int = 1,
    rooms: int = 1,
    groups: int = 1,
    demands: int = 1,
    sessions: int = 2,
    periods: int = 4,
    group_gaps: bool = False,
) -> BuiltSchedule:
    """A one-week Mon-Fri schedule: demand i needs any lecturer, any room and group i % groups."""

    def post(path: str, body: object) -> str:
        response = client.post(path, headers=admin.auth, json=body)
        assert response.status_code == 201, f"{path}: {response.text}"
        return response.json()["id"]

    def resources(key: str, kind: str, count: int) -> tuple[str, list[str]]:
        type_id = post(
            "/api/v1/resource-types", {"key": f"{key}_{uuid4().hex[:8]}", "name": key, "kind": kind}
        )
        ids = [
            post(
                "/api/v1/resources",
                {"resource_type_id": type_id, "code": f"{key.upper()}-{i}", "name": f"{key} {i}"},
            )
            for i in range(count)
        ]
        return type_id, ids

    lecturer_type, lecturer_ids = resources("lecturer", "person", lecturers)
    room_type, _ = resources("room", "space", rooms)
    group_type, group_ids = resources("group", "group", groups)
    schedule_id = post(
        "/api/v1/schedules",
        {
            "name": "Solve term",
            "timezone": "Africa/Kampala",
            "start_date": "2027-01-11",
            "end_date": "2027-01-15",
        },
    )
    base = f"/api/v1/schedules/{schedule_id}"
    slots = [
        {
            "label": f"P{p}",
            "weekdays": [0, 1, 2, 3, 4],
            "start_minute": 480 + 60 * p,
            "duration_minutes": 60,
        }
        for p in range(periods)
    ]
    slot_template = post(
        f"{base}/slot-templates", {"name": "Periods", "definition": {"version": 1, "slots": slots}}
    )
    for d in range(demands):
        post(
            f"{base}/demands",
            {
                "name": f"Course {d}",
                "slot_template_id": slot_template,
                "spec": {
                    "kind": "session",
                    "sessions_per_week": sessions,
                    "requirements": [
                        {"role": "lecturer", "resource_type_id": lecturer_type},
                        {"role": "room", "resource_type_id": room_type},
                        {"role": "group", "fixed_resource_ids": [group_ids[d % groups]]},
                    ],
                },
            },
        )
    if group_gaps:
        add_rule(
            client,
            admin,
            schedule_id,
            "minimize_gaps",
            {"per_minutes": 60},
            weight=1,
            scope={"resource_type_ids": [group_type]},
        )
    return BuiltSchedule(schedule_id, lecturer_type, lecturer_ids, demands * sessions)


def add_rule(
    client: TestClient,
    admin: Account,
    schedule_id: str,
    template_key: str,
    params: dict[str, object],
    *,
    hard: bool = False,
    weight: int = 0,
    scope: dict[str, object] | None = None,
) -> str:
    response = client.post(
        f"/api/v1/schedules/{schedule_id}/constraints",
        headers=admin.auth,
        json={
            "name": f"{template_key} rule",
            "template_key": template_key,
            "template_version": 1,
            "params": params,
            "scope": scope or {},
            "hard": hard,
            "weight": weight,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()["id"]


def slow_schedule(client: TestClient, admin: Account) -> BuiltSchedule:
    """CP-SAT runs to a 60 s limit on this, yet stops within a second of a cancel; gaps over
    every resource instead made presolve slow to honour a stop (calibration in task-4 report)."""
    return build_schedule(
        client,
        admin,
        lecturers=30,
        rooms=30,
        groups=10,
        demands=40,
        sessions=5,
        periods=8,
        group_gaps=True,
    )


def request_run(client: TestClient, admin: Account, schedule_id: str, **body: object) -> str:
    response = client.post(f"/api/v1/schedules/{schedule_id}/solves", headers=admin.auth, json=body)
    assert response.status_code == 202, response.text
    return response.json()["id"]


def solve_now(client: TestClient, admin: Account, schedule_id: str) -> tuple[str, str]:
    """POST a solve and execute it in this thread; returns (run_id, version_id)."""
    run_id = request_run(client, admin, schedule_id)
    status = run_now(cast(FastAPI, client.app), run_id, admin.organisation_id)
    assert status == "succeeded", status
    run = client.get(f"/api/v1/solves/{run_id}", headers=admin.auth).json()
    return run_id, run["version_id"]


def run_now(app: FastAPI, run_id: str, organisation_id: UUID, solve_fn: SolveFn = solve) -> str:
    """Execute a queued run in this thread, as the worker would."""
    settings: Settings = app.state.settings

    async def go() -> str:
        engine = create_db_engine(settings)
        try:
            return await execute_run(engine, settings, UUID(run_id), organisation_id, solve_fn)
        finally:
            await engine.dispose()

    return asyncio.run(go())


@dataclass(frozen=True)
class SseEvent:
    event: str
    data: dict[str, Any]


def parse_sse(lines: Iterable[str]) -> list[SseEvent]:
    """Parse a finished event stream; comment lines (keep-alives) are dropped."""
    events: list[SseEvent] = []
    name, data = "message", ""
    for line in lines:
        if line.startswith(":"):
            continue
        if line == "":
            if data:
                events.append(SseEvent(name, json.loads(data)))
            name, data = "message", ""
        elif line.startswith("event: "):
            name = line[len("event: ") :]
        elif line.startswith("data: "):
            data += line[len("data: ") :]
    return events


class CollectingTransport(Transport):
    def __init__(self) -> None:
        super().__init__()
        self.events: list[Event] = []

    def capture_envelope(self, envelope: Envelope) -> None:
        event = envelope.get_event()
        if event is not None:
            self.events.append(event)

    @property
    def messages(self) -> list[str]:
        return [str(e.get("message") or e.get("logentry", {}).get("message")) for e in self.events]

    @property
    def tags(self) -> list[dict[str, str]]:
        return [dict(e.get("tags", {})) for e in self.events]


def worker_env(monkeypatch: pytest.MonkeyPatch, settings: Settings) -> None:
    """Make load_settings() inside an actor resolve to the test stack (env beats `.env`)."""
    values: dict[str, str] = {
        "DATABASE_URL": str(settings.database_url),
        "REDIS_URL": str(settings.redis_url),
        "JWT_SECRET": settings.jwt_secret.get_secret_value(),
        "WEB_BASE_URL": str(settings.web_base_url),
        "PUBLIC_API_BASE_URL": str(settings.public_api_base_url),
        "S3_ENDPOINT": settings.s3_endpoint,
        "S3_ACCESS_KEY": settings.s3_access_key.get_secret_value(),
        "S3_SECRET_KEY": settings.s3_secret_key.get_secret_value(),
        "S3_BUCKET": settings.s3_bucket,
        "S3_SECURE": str(settings.s3_secure),
        "COOKIE_SECURE": str(settings.cookie_secure),
        "SOLVE_NUM_WORKERS": "1",
        "SOLVE_HEARTBEAT_SECONDS": str(settings.solve_heartbeat_seconds),
    }
    for name, value in values.items():
        monkeypatch.setenv(f"CARTLYF_{name}", value)


@contextmanager
def running_worker(redis_url: str, threads: int) -> Generator[Broker]:
    """A real Dramatiq worker on the solves queue; restores the global broker afterwards."""
    previous = dramatiq.broker.global_broker
    broker = setup_broker(redis_url, timeout_seconds=5)
    loaded = sys.modules.get("cartlyf_api.jobs.actors")
    if loaded:
        importlib.reload(loaded)
    else:
        importlib.import_module("cartlyf_api.jobs.actors")
    worker = Worker(broker, worker_threads=threads, worker_timeout=100)
    worker.start()
    try:
        yield broker
    finally:
        worker.stop()
        broker.close()
        if previous is not None:
            dramatiq.set_broker(previous)


def drain_solves(broker: Broker) -> None:
    broker.join(SOLVE_QUEUE, timeout=60_000)


KAMPALA = ZoneInfo("Africa/Kampala")


def candidate_starts(periods: int = 4) -> list[datetime]:
    """The build_schedule grid: Mon-Fri 2027-01-11..15, periods from 08:00 hourly."""
    monday = datetime(2027, 1, 11, tzinfo=KAMPALA)
    return [
        monday + timedelta(days=d, minutes=480 + 60 * p) for d in range(5) for p in range(periods)
    ]


# Any: response JSON is untyped; tests assert on its values.
def get_version(client: TestClient, admin: Account, version_id: str) -> dict[str, Any]:
    response = client.get(f"/api/v1/solution-versions/{version_id}", headers=admin.auth)
    assert response.status_code == 200, response.text
    return response.json()


def free_start(assignments: list[dict[str, Any]]) -> datetime:
    taken = {datetime.fromisoformat(a["start_at"]) for a in assignments}
    return next(s for s in candidate_starts() if s not in taken)


def move(
    client: TestClient, admin: Account, version_id: str, assignment: dict[str, Any], to: datetime
) -> Any:
    return client.post(
        f"/api/v1/solution-versions/{version_id}/drafts",
        headers=admin.auth,
        json={
            "changes": [
                {
                    "activity_id": assignment["activity_id"],
                    "start_at": to.isoformat(),
                    "resources": assignment["resources"],
                }
            ]
        },
    )


def publish(client: TestClient, admin: Account, version_id: str) -> Any:
    return client.post(f"/api/v1/solution-versions/{version_id}/publish", headers=admin.auth)
