import asyncio
from typing import cast
from uuid import uuid4

import pytest
from sqlalchemy.ext.asyncio import AsyncEngine

from cartlyf_api.email import outbox
from cartlyf_api.email.outbox import QueuedEmail, deliver_all
from cartlyf_api.email.provider import ConsoleEmailProvider, EmailProvider


def test_deliver_all_keeps_going_after_an_unexpected_failure(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first, second = QueuedEmail(uuid4(), uuid4()), QueuedEmail(uuid4(), uuid4())
    delivered: list[QueuedEmail] = []

    async def flaky(_engine: AsyncEngine, _provider: EmailProvider, queued: QueuedEmail) -> bool:
        if queued is first:
            raise OSError("database went away")
        delivered.append(queued)
        return True

    monkeypatch.setattr(outbox, "deliver", flaky)
    engine = cast(AsyncEngine, object())
    asyncio.run(deliver_all(engine, ConsoleEmailProvider(), [first, second]))
    assert delivered == [second]
