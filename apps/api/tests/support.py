import asyncio
import re
from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any, cast
from uuid import UUID, uuid4

import httpx2 as httpx
from alembic.config import Config
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.auth.cookies import REFRESH_COOKIE
from cartlyf_api.email.provider import ConsoleEmailProvider
from cartlyf_api.examples import EXAMPLE_IDS
from cartlyf_api.settings import Settings

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
    execute_many(
        url,
        [
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
        ],
    )
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
    return {}


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
