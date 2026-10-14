import asyncio
import time
from collections.abc import AsyncGenerator, Awaitable, Callable
from contextlib import asynccontextmanager
from typing import Protocol, cast
from uuid import UUID

import asyncpg  # pyright: ignore[reportMissingTypeStubs]
import structlog
from sqlalchemy.engine import make_url

from cartlyf_api.settings import Settings

log = structlog.get_logger()

CHANNEL = "solve_run"
# A dropped listener is retried at most this often; streams still poll on every heartbeat.
RECONNECT_SECONDS = 15


class ListenConnection(Protocol):
    async def add_listener(self, channel: str, callback: Callable[..., None]) -> None: ...

    def is_closed(self) -> bool: ...

    async def close(self) -> None: ...


Connect = Callable[[], Awaitable[ListenConnection]]


def asyncpg_connector(settings: Settings) -> Connect:
    """Dedicated connections outside the SQLAlchemy pool, so a LISTEN never holds a pool slot."""
    dsn = make_url(str(settings.database_url)).set(drivername="postgresql")
    rendered = dsn.render_as_string(hide_password=False)
    timeout = settings.db_timeout_seconds

    # asyncpg ships no type stubs; its connection satisfies ListenConnection.
    open_connection = cast(
        Callable[..., Awaitable[ListenConnection]],
        asyncpg.connect,  # pyright: ignore[reportUnknownMemberType]
    )

    async def connect() -> ListenConnection:
        return await open_connection(rendered, timeout=timeout, command_timeout=timeout)

    return connect


class SolveNotifier:
    """One LISTEN connection per process, fanning solve_run notifications out to open streams."""

    def __init__(self, connect: Connect) -> None:
        self._connect = connect
        self._connection: ListenConnection | None = None
        self._lock = asyncio.Lock()
        self._next_attempt = 0.0
        self._subscribers: dict[str, set[asyncio.Event]] = {}

    @asynccontextmanager
    async def subscribe(self, run_id: UUID) -> AsyncGenerator[asyncio.Event]:
        key, event = str(run_id), asyncio.Event()
        self._subscribers.setdefault(key, set()).add(event)
        try:
            await self.ensure_listening()
            yield event
        finally:
            events = self._subscribers.get(key)
            if events is not None:
                events.discard(event)
                if not events:
                    del self._subscribers[key]

    def subscriber_count(self) -> int:
        return sum(len(events) for events in self._subscribers.values())

    async def ensure_listening(self) -> None:
        if self._listening() or time.monotonic() < self._next_attempt:
            return
        async with self._lock:
            if self._listening() or time.monotonic() < self._next_attempt:
                return
            connection: ListenConnection | None = None
            try:
                connection = await self._connect()
                await connection.add_listener(CHANNEL, self._on_notify)
            except Exception:  # best effort: streams fall back to polling on every heartbeat
                self._next_attempt = time.monotonic() + RECONNECT_SECONDS
                log.warning("solve_notifier_listen_failed", exc_info=True)
                if connection is not None and not connection.is_closed():
                    await connection.close()
                return
            self._connection = connection

    async def close(self) -> None:
        connection, self._connection = self._connection, None
        if connection is not None and not connection.is_closed():
            await connection.close()

    def _listening(self) -> bool:
        if self._connection is not None and self._connection.is_closed():
            log.warning("solve_notifier_connection_lost")
            self._connection = None
        return self._connection is not None

    def _on_notify(self, _conn: object, _pid: int, _channel: str, payload: str) -> None:
        for event in self._subscribers.get(payload, ()):
            event.set()
