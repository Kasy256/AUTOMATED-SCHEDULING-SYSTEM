import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import Connection
from sqlalchemy.ext.asyncio import create_async_engine

config = context.config
if config.config_file_name and "database_url" not in config.attributes:
    fileConfig(config.config_file_name)


def _url() -> str:
    # Migrations run as cartlyf_owner, never as the app role.
    url = config.attributes.get("database_url") or os.environ["CARTLYF_MIGRATION_DATABASE_URL"]
    return str(url)


def _migrate(connection: Connection) -> None:
    context.configure(connection=connection)
    with context.begin_transaction():
        context.run_migrations()


async def _run() -> None:
    engine = create_async_engine(_url())
    try:
        async with engine.connect() as conn:
            await conn.run_sync(_migrate)
            await conn.commit()
    finally:
        await engine.dispose()


if context.is_offline_mode():
    raise SystemExit("Offline migrations are not supported; run against a database.")
asyncio.run(_run())
