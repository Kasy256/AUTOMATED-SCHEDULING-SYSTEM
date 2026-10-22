import asyncio
import json
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Protocol

import structlog

from cartlyf_api.settings import Settings

log = structlog.get_logger()


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailProvider(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailProvider:
    """Dev/test backend. Logs whole messages, links included, so never use it in production."""

    def __init__(self) -> None:
        self.sent: list[EmailMessage] = []

    async def send(self, message: EmailMessage) -> None:
        self.sent.append(message)
        log.info("email_console", to=message.to, subject=message.subject, body=message.body)


class EmailDeliveryError(Exception):
    pass


class ResendEmailProvider:
    """Sends through Resend's HTTPS API (https://resend.com/docs/api-reference/emails)."""

    def __init__(self, api_url: str, api_key: str, sender: str) -> None:
        self._endpoint = api_url.rstrip("/") + "/emails"
        self._api_key = api_key
        self._sender = sender

    async def send(self, message: EmailMessage) -> None:
        await asyncio.to_thread(self._post, message)

    def _post(self, message: EmailMessage) -> None:
        payload = {
            "from": self._sender,
            "to": [message.to],
            "subject": message.subject,
            "text": message.body,
        }
        request = urllib.request.Request(
            self._endpoint,
            data=json.dumps(payload).encode(),
            headers={
                "Authorization": f"Bearer {self._api_key}",
                "Content-Type": "application/json",
                "User-Agent": "cartlyf-api",
            },
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=10):
                pass
        except urllib.error.HTTPError as exc:
            raise EmailDeliveryError(f"Resend answered {exc.code}") from None
        except (urllib.error.URLError, TimeoutError) as exc:
            raise EmailDeliveryError(f"Resend unreachable: {type(exc).__name__}") from None


def make_email_provider(settings: Settings) -> EmailProvider:
    if settings.email_provider == "console":
        return ConsoleEmailProvider()
    # The settings validator guarantees both are present for resend.
    assert settings.resend_api_key is not None and settings.email_from is not None
    return ResendEmailProvider(
        str(settings.resend_api_url),
        settings.resend_api_key.get_secret_value(),
        settings.email_from,
    )
