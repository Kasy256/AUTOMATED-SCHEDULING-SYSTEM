import asyncio
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

from alembic.config import Config
from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

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
