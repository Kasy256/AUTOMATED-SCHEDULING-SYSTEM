from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from cartlyf_api.industry_templates.models import IndustryTemplate


async def latest_templates(session: AsyncSession) -> Sequence[IndustryTemplate]:
    rows = await session.scalars(
        select(IndustryTemplate).order_by(IndustryTemplate.key, IndustryTemplate.version.desc())
    )
    latest: dict[str, IndustryTemplate] = {}
    for row in rows:
        latest.setdefault(row.key, row)
    return list(latest.values())


async def latest_template(session: AsyncSession, key: str) -> IndustryTemplate | None:
    return await session.scalar(
        select(IndustryTemplate)
        .where(IndustryTemplate.key == key)
        .order_by(IndustryTemplate.version.desc())
        .limit(1)
    )
