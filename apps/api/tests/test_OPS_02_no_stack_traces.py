import json
from collections.abc import Iterator
from typing import cast
from uuid import uuid4

import pytest
import sentry_sdk
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cartlyf_api.main import create_app
from cartlyf_api.sentry import report_failed_verification, sentry_options
from support import (
    CollectingTransport,
    Operation,
    build_world,
    make_settings,
    openapi_operations,
    ordered,
    substitute_ids,
)

LEAKS = ("Traceback", 'File "', "sqlalchemy", "asyncpg", "pydantic_core", "psycopg")
BAD_IDS = ("not-a-uuid", "00000000-0000-0000-0000-000000000000", "9" * 5000)
HOSTILE = "\u0000'\";--"
# Valid text that reaches the database and comes back out; long enough to overflow a btree index.
QUOTED = "'\";--<script>"
LONG = "x" * 10_000


def _hostile(value: object, ints: bool = True, text: str = HOSTILE) -> object:
    if isinstance(value, bool):
        return value
    if isinstance(value, str):
        return text
    if isinstance(value, int) and ints:
        return 2**63
    if isinstance(value, list):
        return [_hostile(v, ints, text) for v in cast(list[object], value)]
    if isinstance(value, dict):
        return {k: _hostile(v, ints, text) for k, v in cast(dict[str, object], value).items()}
    return value


def _bodies(op: Operation, ids: dict[str, str]) -> list[object]:
    if op.method in ("GET", "DELETE"):
        return []
    bodies: list[object] = [{}, [], "x", {"name": None}]
    if op.body is not None:
        example = substitute_ids(op.body, ids)
        # Hostile strings with valid numbers, so strings get past validation to the database.
        bodies += [_hostile(example), _hostile(example, ints=False)]
        bodies += [_hostile(example, ints=False, text=t) for t in (QUOTED, LONG)]
    return bodies


@pytest.mark.integration
def test_OPS_02_fuzzed_requests_never_leak_internals(client: TestClient, app: FastAPI) -> None:
    world = build_world(client, app)
    auth = world.a_admin.auth
    failures: list[str] = []
    probes: list[str] = []

    def probe(label: str, method: str, url: str, **kwargs: object) -> None:
        probes.append(label)
        headers = auth | cast(dict[str, str], kwargs.pop("headers", {}))
        response = client.request(method, url, headers=headers, **kwargs)  # pyright: ignore[reportArgumentType]
        leaked = [marker for marker in LEAKS if marker in response.text]
        if response.status_code >= 500 or leaked:
            failures.append(f"{label} -> {response.status_code} {leaked} {response.text[:200]}")

    for op in ordered(openapi_operations(app)):
        route = f"{op.method} {op.path}"
        for bad in BAD_IDS if op.path_params else ():
            url = op.path.format(**dict.fromkeys(op.path_params, bad))
            probe(f"{route} id={bad[:12]}", op.method, url, json=None)
        if op.method in ("GET", "DELETE"):
            continue
        url = op.path.format(**{name: world.a_ids[name] for name in op.path_params})
        for body in _bodies(op, world.a_ids):
            probe(f"{route} body={json.dumps(body)[:60]}", op.method, url, json=body)
        probe(
            f"{route} invalid json",
            op.method,
            url,
            content=b'{"name": ',
            headers={"Content-Type": "application/json"},
        )
    assert not failures, "\n".join(failures)
    # Guards against the fuzz silently probing nothing.
    assert len(probes) > 300, len(probes)


def _boom_app() -> FastAPI:
    app = create_app(
        make_settings("postgresql+asyncpg://u:p@localhost:1/x", "redis://localhost:1/0")
    )

    async def boom() -> None:
        raise RuntimeError("secret internal detail")

    app.add_api_route("/boom", boom)
    return app


@pytest.fixture
def scrubbed_sentry() -> Iterator[CollectingTransport]:
    settings = make_settings(
        "postgresql+asyncpg://u:p@localhost:1/x",
        "redis://localhost:1/0",
        sentry_dsn="https://k@o0.ingest.sentry.io/0",
        release="abc123",
    )
    transport = CollectingTransport()
    sentry_sdk.init(**sentry_options(settings), transport=transport)
    try:
        yield transport
    finally:
        sentry_sdk.init()


def test_OPS_02_unhandled_error_reaches_sentry(scrubbed_sentry: CollectingTransport) -> None:
    with TestClient(_boom_app(), raise_server_exceptions=False) as client:
        response = client.get("/boom")
    assert response.status_code == 500
    assert "secret internal detail" not in response.text
    exceptions = [e.get("exception", {})["values"][-1]["type"] for e in scrubbed_sentry.events]
    assert exceptions == ["RuntimeError"]
    assert scrubbed_sentry.events[0].get("environment") == "local"
    assert scrubbed_sentry.events[0].get("release") == "abc123"


def test_sentry_event_is_scrubbed(scrubbed_sentry: CollectingTransport) -> None:
    # Random values: Sentry's source context would otherwise show literals from this file.
    feed, query, bearer, cookie, password = (uuid4().hex for _ in range(5))
    app = _boom_app()

    async def leaky(token: str) -> None:
        raise RuntimeError("boom")

    app.add_api_route("/api/v1/calendar/{token}.ics", leaky, methods=["POST"])
    with TestClient(app, raise_server_exceptions=False) as client:
        client.post(
            f"/api/v1/calendar/{feed}.ics?code={query}",
            headers={"Authorization": f"Bearer {bearer}", "Cookie": f"cartlyf_refresh={cookie}"},
            json={"password": password},
        )
    serialised = json.dumps(scrubbed_sentry.events, default=str)
    assert scrubbed_sentry.events
    for secret in (feed, query, bearer, cookie, password):
        assert secret not in serialised


def test_failed_verification_has_tag_and_fingerprint(scrubbed_sentry: CollectingTransport) -> None:
    report_failed_verification(uuid4(), uuid4(), 2)
    [event] = scrubbed_sentry.events
    assert event.get("fingerprint") == ["solve_failed_verification"]
    assert event.get("level") == "error"
