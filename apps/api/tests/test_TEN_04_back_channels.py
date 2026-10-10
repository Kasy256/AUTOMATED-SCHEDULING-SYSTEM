import asyncio

import pytest
from sqlalchemy import select, update
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.email.outbox import QueuedEmail, deliver, enqueue
from cartlyf_api.email.provider import ConsoleEmailProvider, EmailMessage
from cartlyf_api.orgs.models import Membership, MembershipRole
from cartlyf_api.tenancy import scoped_transaction
from support import APP, db_url, fetch, seed_org, superuser_url

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


def test_TEN_04_email_delivery_is_scoped_to_its_recipient(migrated_pg: PostgresContainer) -> None:
    a = seed_org(superuser_url(migrated_pg), "Ten04 Mail A")
    b = seed_org(superuser_url(migrated_pg), "Ten04 Mail B")

    async def run() -> None:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        provider = ConsoleEmailProvider()
        try:
            async with scoped_transaction(engine, None, b.user_id) as session:
                message = EmailMessage("b@example.com", "Subject", "Body")
                queued_b = await enqueue(session, b.user_id, message)
            forged = QueuedEmail(queued_b.outbox_id, a.user_id)
            assert await deliver(engine, provider, forged) is False
            assert provider.sent == []
            assert await deliver(engine, provider, queued_b) is True
            assert provider.sent == [EmailMessage("b@example.com", "Subject", "Body")]
            assert await deliver(engine, provider, queued_b) is False
        finally:
            await engine.dispose()

    asyncio.run(run())


def test_failed_send_is_recorded_for_retry(migrated_pg: PostgresContainer) -> None:
    a = seed_org(superuser_url(migrated_pg), "Ten04 Fail")

    class BrokenProvider:
        async def send(self, message: EmailMessage) -> None:
            raise ConnectionError("smtp down")

    async def run() -> QueuedEmail:
        engine = create_async_engine(db_url(migrated_pg, *APP))
        try:
            async with scoped_transaction(engine, None, a.user_id) as session:
                queued = await enqueue(session, a.user_id, EmailMessage("a@example.com", "s", "b"))
            assert await deliver(engine, BrokenProvider(), queued) is False
            return queued
        finally:
            await engine.dispose()

    queued = asyncio.run(run())
    rows = fetch(
        superuser_url(migrated_pg),
        f"SELECT attempts, last_error, sent_at FROM email_outbox WHERE id = '{queued.outbox_id}'",
    )
    assert rows == [(1, "ConnectionError", None)]
