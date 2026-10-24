from datetime import datetime
from uuid import UUID

from sqlalchemy import func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class EmailOutbox(Base):
    __tablename__ = "email_outbox"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID]
    to_address: Mapped[str] = mapped_column(CITEXT)
    subject: Mapped[str]
    body: Mapped[str]
    attempts: Mapped[int] = mapped_column(server_default=text("0"))
    last_error: Mapped[str | None]
    sent_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
