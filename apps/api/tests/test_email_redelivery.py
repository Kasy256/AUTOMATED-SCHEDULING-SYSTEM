import asyncio
from collections.abc import Callable, Coroutine
from typing import Any
from uuid import UUID, uuid4

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine
from testcontainers.community.postgres import PostgresContainer

from cartlyf_api.email.outbox import QueuedEmail, deliver, enqueue, redeliver_pending
from cartlyf_api.email.provider import EmailMessage
from cartlyf_api.email.redeliver import run_sweep
from cartlyf_api.tenancy import scoped_transaction
from support import APP, db_url, execute, fetch, make_settings, signup_and_confirm, superuser_url

pytestmark = pytest.mark.integration


class Recording:
    def __init__(self, fail: bool = False) -> None:
        self.fail = fail
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        if self.fail:
            raise OSError("provider down")
        self.sent.append(message)


def _with_engine(
    pg: PostgresContainer, fn: Callable[[AsyncEngine], Coroutine[Any, Any, Any]]
) -> Any:
    async def run() -> Any:
        engine = create_async_engine(db_url(pg, *APP))
        try:
            return await fn(engine)
        finally:
            await engine.dispose()

    return asyncio.run(run())


def _user_id(pg: PostgresContainer, email: str) -> UUID:
    return fetch(superuser_url(pg), f"SELECT id FROM app_user WHERE email = '{email}'")[0][0]


def _failed_email(pg: PostgresContainer, user_id: UUID, subject: str) -> QueuedEmail:
    async def go(engine: AsyncEngine) -> QueuedEmail:
        async with scoped_transaction(engine, None, user_id) as session:
            queued = await enqueue(session, user_id, EmailMessage("x@example.test", subject, "b"))
        assert not await deliver(engine, Recording(fail=True), queued)
        return queued

    return _with_engine(pg, go)


def test_redelivery_sends_each_failed_email_once(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    subjects = [f"retry-{uuid4().hex}" for _ in range(2)]
    for org, subject in zip(("Org A", "Org B"), subjects, strict=True):
        account = signup_and_confirm(client, app, org_name=org)
        _failed_email(migrated_pg, _user_id(migrated_pg, account.email), subject)

    provider = Recording()
    _with_engine(migrated_pg, lambda e: redeliver_pending(e, provider, max_attempts=5))
    assert sorted(m.subject for m in provider.sent if m.subject in subjects) == sorted(subjects)

    again = Recording()
    _with_engine(migrated_pg, lambda e: redeliver_pending(e, again, max_attempts=5))
    assert not [m for m in again.sent if m.subject in subjects]


def test_redelivery_gives_up_after_max_attempts(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    subject = f"exhausted-{uuid4().hex}"
    queued = _failed_email(migrated_pg, _user_id(migrated_pg, account.email), subject)
    execute(
        superuser_url(migrated_pg),
        f"UPDATE email_outbox SET attempts = 5 WHERE id = '{queued.outbox_id}'",
    )
    provider = Recording()
    _with_engine(migrated_pg, lambda e: redeliver_pending(e, provider, max_attempts=5))
    assert subject not in [m.subject for m in provider.sent]


def test_pending_lookup_returns_ids_only_without_context(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    queued = _failed_email(migrated_pg, _user_id(migrated_pg, account.email), "ids-only")

    async def look(engine: AsyncEngine) -> tuple[int, list[str], set[UUID]]:
        async with scoped_transaction(engine) as session:
            visible = (await session.execute(text("SELECT count(*) FROM email_outbox"))).scalar()
            result = await session.execute(text("SELECT * FROM auth.pending_emails(5, 1000)"))
            return int(visible or 0), list(result.keys()), {row[0] for row in result}

    visible, columns, ids = _with_engine(migrated_pg, look)
    assert visible == 0
    assert columns == ["outbox_id", "user_id"]
    assert queued.outbox_id in ids


def test_redelivery_job_sweeps_with_the_configured_provider(
    client: TestClient, app: FastAPI, migrated_pg: PostgresContainer
) -> None:
    account = signup_and_confirm(client, app)
    _failed_email(migrated_pg, _user_id(migrated_pg, account.email), f"job-{uuid4().hex}")
    settings = make_settings(db_url(migrated_pg, *APP), "redis://localhost:1/0")
    assert settings.email_max_attempts == 5
    assert asyncio.run(run_sweep(settings)) >= 1
