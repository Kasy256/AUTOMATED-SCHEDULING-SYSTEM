import asyncio
from collections.abc import Callable
from uuid import uuid4

import pytest

from cartlyf_api.solves import notifier as notifier_module
from cartlyf_api.solves.notifier import ListenConnection, SolveNotifier


class FakeConnection:
    def __init__(self) -> None:
        self.callback: Callable[..., None] | None = None
        self.closed = False

    async def add_listener(self, channel: str, callback: Callable[..., None]) -> None:
        self.callback = callback

    def is_closed(self) -> bool:
        return self.closed

    async def close(self) -> None:
        self.closed = True


def test_notifications_wake_only_that_runs_subscribers() -> None:
    connections: list[FakeConnection] = []

    async def connect() -> ListenConnection:
        connections.append(FakeConnection())
        return connections[-1]

    async def go() -> None:
        notifier = SolveNotifier(connect)
        run, other = uuid4(), uuid4()
        async with notifier.subscribe(run) as mine, notifier.subscribe(other) as theirs:
            assert len(connections) == 1
            callback = connections[0].callback
            assert callback is not None
            callback(None, 1, "solve_run", str(run))
            assert mine.is_set() and not theirs.is_set()
        assert notifier.subscriber_count() == 0
        await notifier.close()
        assert connections[0].closed

    asyncio.run(go())


def test_dropped_listener_reconnects_lazily_and_failures_do_not_raise(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    connections: list[FakeConnection] = []
    fail = [True]

    async def connect() -> ListenConnection:
        if fail[0]:
            raise OSError("database unavailable")
        connections.append(FakeConnection())
        return connections[-1]

    async def go() -> None:
        notifier = SolveNotifier(connect)
        monkeypatch.setattr(notifier_module, "RECONNECT_SECONDS", 0)
        async with notifier.subscribe(uuid4()):
            assert connections == []
            fail[0] = False
            await notifier.ensure_listening()
            assert len(connections) == 1
            connections[0].closed = True
            await notifier.ensure_listening()
            assert len(connections) == 2

    asyncio.run(go())
