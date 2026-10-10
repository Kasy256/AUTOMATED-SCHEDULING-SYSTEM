import asyncio

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.orgs.models import Membership, MembershipRole
from cartlyf_api.tenancy import scoped_transaction
from support import APP, db_url, seed_org, superuser_url

pytestmark = pytest.mark.integration


def test_TEN_04_scoped_job_cannot_touch_other_org(migrated_pg: PostgresContainer) -> None:
    a = seed_org(superuser_url(migrated_pg), "Ten04 A")
    b = seed_org(superuser_url(migrated_pg), "Ten04 B")

    async def run() -> None:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            async with scoped_transaction(engine, a.organisation_id, a.user_id) as session:
                assert await session.get(Membership, a.membership_id) is not None
                assert await session.get(Membership, b.membership_id) is None
                updated = await session.scalars(
                    update(Membership)
                    .where(Membership.id == b.membership_id)
                    .values(status="invited")
                    .returning(Membership.id)
                )
                assert updated.all() == []
                ids = (await session.scalars(select(Membership.organisation_id))).all()
                assert set(ids) == {a.organisation_id}
            with pytest.raises(DBAPIError, match="row-level security"):
                async with scoped_transaction(engine, a.organisation_id, a.user_id) as session:
                    session.add(
                        MembershipRole(
                            organisation_id=b.organisation_id,
                            membership_id=b.membership_id,
                            role="viewer",
                        )
                    )
        finally:
            await engine.dispose()

    asyncio.run(run())
