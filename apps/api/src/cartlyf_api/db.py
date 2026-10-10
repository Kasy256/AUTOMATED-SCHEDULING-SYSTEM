from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cartlyf_api.settings import Settings


def create_db_engine(settings: Settings) -> AsyncEngine:
    # Bounded waits: asyncpg's default 60s connect timeout would outlast any health-check probe.
    timeout = settings.db_timeout_seconds
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"timeout": timeout, "command_timeout": timeout},
    )
