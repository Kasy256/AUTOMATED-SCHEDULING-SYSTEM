from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from uuid import UUID, uuid4

import structlog
from sqlalchemy import insert, text
from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession

from cartlyf_api.email.models import EmailOutbox
from cartlyf_api.email.provider import EmailMessage, EmailProvider
from cartlyf_api.tenancy import scoped_transaction

log = structlog.get_logger()


@dataclass(frozen=True)
class QueuedEmail:
    outbox_id: UUID
    user_id: UUID


async def enqueue(session: AsyncSession, user_id: UUID, message: EmailMessage) -> QueuedEmail:
    outbox_id = uuid4()
    await session.execute(
        insert(EmailOutbox).values(
            id=outbox_id,
            user_id=user_id,
            to_address=message.to,
            subject=message.subject,
            body=message.body,
        )
    )
    return QueuedEmail(outbox_id, user_id)


async def deliver(engine: AsyncEngine, provider: EmailProvider, queued: QueuedEmail) -> bool:
    """Send one outbox row as its recipient; False if not visible, already sent, or failed."""
    async with scoped_transaction(engine, None, queued.user_id) as session:
        row = await session.get(EmailOutbox, queued.outbox_id, with_for_update=True)
        if row is None or row.sent_at is not None:
            return False
        row.attempts += 1
        try:
            await provider.send(EmailMessage(row.to_address, row.subject, row.body))
        except Exception as exc:  # any provider failure is recorded on the row for a retry
            row.last_error = type(exc).__name__
            log.warning("email_delivery_failed", outbox_id=str(row.id), exc_info=True)
            return False
        row.sent_at = datetime.now(UTC)
        return True


async def deliver_all(
    engine: AsyncEngine, provider: EmailProvider, queued: Iterable[QueuedEmail]
) -> None:
    """Deliver each email in turn; one failure (DB or otherwise) must not drop the rest."""
    for email in queued:
        try:
            await deliver(engine, provider, email)
        except Exception:
            log.exception("email_delivery_crashed", outbox_id=str(email.outbox_id))


# One sweep's cap; the next run takes the rest.
_SWEEP_LIMIT = 500
_PENDING = text("SELECT outbox_id, user_id FROM auth.pending_emails(:max_attempts, :limit)")


async def redeliver_pending(engine: AsyncEngine, provider: EmailProvider, max_attempts: int) -> int:
    """Retry every unsent email below the attempt cap; returns how many were sent."""
    async with scoped_transaction(engine) as session:
        rows = (
            await session.execute(_PENDING, {"max_attempts": max_attempts, "limit": _SWEEP_LIMIT})
        ).all()
    sent = 0
    for outbox_id, user_id in rows:
        try:
            sent += await deliver(engine, provider, QueuedEmail(outbox_id, user_id))
        except Exception:
            log.exception("email_redelivery_crashed", outbox_id=str(outbox_id))
    return sent
