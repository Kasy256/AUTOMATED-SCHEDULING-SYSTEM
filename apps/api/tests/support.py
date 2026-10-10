import asyncio
from pathlib import Path
from typing import Any

from alembic.config import Config
from sqlalchemy import Row, text
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


def fetch(url: str, sql: str) -> list[Row[Any]]:
    async def run() -> list[Row[Any]]:
        engine = create_async_engine(url)
        try:
            async with engine.begin() as conn:
                return list((await conn.execute(text(sql))).all())
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
