from dataclasses import dataclass
from typing import Protocol

import structlog

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
