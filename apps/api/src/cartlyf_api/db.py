from datetime import datetime
from typing import Any, ClassVar

from sqlalchemy import DateTime
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from sqlalchemy.orm import DeclarativeBase

from cartlyf_api.settings import Settings

# Any: JSONB documents, validated by Pydantic models on the way in and out.
JsonDict = dict[str, Any]


class Base(DeclarativeBase):
    # Any: SQLAlchemy's own annotation for this mapping.
    type_annotation_map: ClassVar[dict[Any, Any]] = {datetime: DateTime(timezone=True)}


def create_db_engine(settings: Settings) -> AsyncEngine:
    # Bounded waits: asyncpg's default 60s connect timeout would outlast any health-check probe.
    timeout = settings.db_timeout_seconds
    return create_async_engine(
        str(settings.database_url),
        pool_pre_ping=True,
        connect_args={"timeout": timeout, "command_timeout": timeout},
    )
