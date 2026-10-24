import asyncio
import json
import threading
from collections.abc import Iterator
from dataclasses import dataclass, field
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from cartlyf_api.email.provider import (
    ConsoleEmailProvider,
    EmailDeliveryError,
    EmailMessage,
    ResendEmailProvider,
    make_email_provider,
)
from support import make_settings

MESSAGE = EmailMessage("a@x.test", "S", "B")


@dataclass
class FakeResend:
    url: str
    status: int = 200
    statuses: list[int] = field(default_factory=list[int])  # answered first, in order
    requests: list[tuple[str, dict[str, str], object]] = field(
        default_factory=list[tuple[str, dict[str, str], object]]
    )


@pytest.fixture
def resend() -> Iterator[FakeResend]:
    fake = FakeResend("")

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            fake.requests.append((self.path, dict(self.headers.items()), body))
            self.send_response(fake.statuses.pop(0) if fake.statuses else fake.status)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"id": "1"}')

        def log_message(self, format: str, *args: object) -> None:
            pass

    server = HTTPServer(("127.0.0.1", 0), Handler)
    fake.url = f"http://127.0.0.1:{server.server_port}"
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield fake
    finally:
        server.shutdown()


def test_resend_posts_message(resend: FakeResend) -> None:
    provider = ResendEmailProvider(resend.url, "k", "Cartlyf <no-reply@x.test>")
    asyncio.run(provider.send(MESSAGE))
    [(path, headers, body)] = resend.requests
    assert path == "/emails"
    assert headers["Authorization"] == "Bearer k"
    assert body == {
        "from": "Cartlyf <no-reply@x.test>",
        "to": ["a@x.test"],
        "subject": "S",
        "text": "B",
    }


def test_resend_error_raises_delivery_error(resend: FakeResend) -> None:
    resend.status = 422
    provider = ResendEmailProvider(resend.url, "secret-key", "no-reply@x.test")
    with pytest.raises(EmailDeliveryError) as raised:
        asyncio.run(provider.send(MESSAGE))
    assert "422" in str(raised.value)
    assert "secret-key" not in str(raised.value)


def test_unreachable_resend_raises_delivery_error() -> None:
    provider = ResendEmailProvider("http://127.0.0.1:1", "k", "no-reply@x.test")
    with pytest.raises(EmailDeliveryError):
        asyncio.run(provider.send(MESSAGE))


def test_make_email_provider_picks_by_setting() -> None:
    url = "postgresql+asyncpg://u:p@h/db"
    assert isinstance(make_email_provider(make_settings(url, "redis://h/0")), ConsoleEmailProvider)
    resend = make_settings(
        url, "redis://h/0", email_provider="resend", resend_api_key="k", email_from="n@x.test"
    )
    assert isinstance(make_email_provider(resend), ResendEmailProvider)


@pytest.mark.parametrize("transient", [429, 500, 503])
def test_resend_retries_transient_failures(resend: FakeResend, transient: int) -> None:
    resend.statuses = [transient, transient]
    provider = ResendEmailProvider(resend.url, "k", "n@x.test", retry_delays_s=(0, 0))
    asyncio.run(provider.send(MESSAGE))
    assert len(resend.requests) == 3


def test_resend_gives_up_after_the_last_retry(resend: FakeResend) -> None:
    resend.status = 429
    provider = ResendEmailProvider(resend.url, "k", "n@x.test", retry_delays_s=(0, 0))
    with pytest.raises(EmailDeliveryError, match="429"):
        asyncio.run(provider.send(MESSAGE))
    assert len(resend.requests) == 3


def test_resend_does_not_retry_a_rejected_message(resend: FakeResend) -> None:
    resend.status = 422
    provider = ResendEmailProvider(resend.url, "k", "n@x.test", retry_delays_s=(0, 0))
    with pytest.raises(EmailDeliveryError):
        asyncio.run(provider.send(MESSAGE))
    assert len(resend.requests) == 1
