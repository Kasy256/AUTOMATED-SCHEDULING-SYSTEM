from datetime import datetime
from uuid import UUID

from sqlalchemy import LargeBinary, func
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class CalendarFeed(Base):
    __tablename__ = "calendar_feed"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    revoked_at: Mapped[datetime | None]
