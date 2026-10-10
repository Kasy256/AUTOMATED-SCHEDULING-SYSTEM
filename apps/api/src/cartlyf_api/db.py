from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from cartlyf_api.settings import Settings


def create_db_engine(settings: Settings) -> AsyncEngine:
    return create_async_engine(str(settings.database_url), pool_pre_ping=True)
