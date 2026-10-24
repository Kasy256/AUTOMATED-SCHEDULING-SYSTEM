import json
import threading
from collections.abc import Callable, Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from tools.smoke import smoke

WEB_ORIGIN_HEADER = "Access-Control-Allow-Origin"
SAFE_ROLE = {"current_user": "cartlyf_app", "rolsuper": False, "rolbypassrls": False}

Handler = Callable[[BaseHTTPRequestHandler], None]


def _serve(get: Handler, options: Handler | None = None) -> Iterator[str]:
    class H(BaseHTTPRequestHandler):
        def do_GET(self) -> None:
            get(self)

        def do_OPTIONS(self) -> None:
            assert options is not None
            options(self)

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), H)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        yield f"http://127.0.0.1:{server.server_port}"
    finally:
        server.shutdown()


def _reply(h: BaseHTTPRequestHandler, status: int, body: bytes, **headers: str) -> None:
    h.send_response(status)
    for name, value in headers.items():
        h.send_header(name.replace("_", "-"), value)
    h.send_header("Content-Length", str(len(body)))
    h.end_headers()
    h.wfile.write(body)


class Stack:
    def __init__(self) -> None:
        self.health_status = 200
        self.role = SAFE_ROLE
        self.allow_origin: str | None = None
        self.page = b'<!doctype html><div id="root"></div>'


@pytest.fixture
def stack() -> Stack:
    return Stack()


@pytest.fixture
def web(stack: Stack) -> Iterator[str]:
    yield from _serve(lambda h: _reply(h, 200, stack.page, Content_Type="text/html"))


@pytest.fixture
def api(stack: Stack, web: str) -> Iterator[str]:
    def get(h: BaseHTTPRequestHandler) -> None:
        if h.path != "/api/v1/health":
            _reply(h, 404, b"{}")
            return
        body = {"status": "ok", "database": stack.role} if stack.health_status == 200 else {}
        _reply(h, stack.health_status, json.dumps(body).encode(), Content_Type="application/json")

    def options(h: BaseHTTPRequestHandler) -> None:
        origin = stack.allow_origin or h.headers["Origin"]
        _reply(
            h, 200, b"", **{WEB_ORIGIN_HEADER: origin, "Access-Control-Allow-Credentials": "true"}
        )

    yield from _serve(get, options)


def test_smoke_passes_on_healthy_stack(api: str, web: str) -> None:
    assert smoke(api, web) == []


def test_smoke_reports_each_failure(stack: Stack, api: str, web: str) -> None:
    stack.health_status = 503
    stack.allow_origin = "https://evil.example"
    stack.page = b"<html>maintenance</html>"
    failures = smoke(api, web)
    assert len(failures) == 3, failures
    assert any("health" in f for f in failures)
    assert any("CORS" in f for f in failures)
    assert any("root" in f for f in failures)


def test_smoke_flags_an_unsafe_database_role(stack: Stack, api: str, web: str) -> None:
    stack.role = SAFE_ROLE | {"rolbypassrls": True}
    assert any("role" in f for f in smoke(api, web))
