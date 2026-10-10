from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine

from cartlyf_api.health.schemas import DbRole

_ROLE_SQL = text(
    "SELECT current_user, rolsuper, rolbypassrls FROM pg_roles WHERE rolname = current_user"
)


async def fetch_db_role(engine: AsyncEngine) -> DbRole:
    async with engine.connect() as conn:
        row = (await conn.execute(_ROLE_SQL)).one()
    return DbRole(current_user=row[0], rolsuper=row[1], rolbypassrls=row[2])
