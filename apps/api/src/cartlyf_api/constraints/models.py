from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class ConstraintInstanceRow(Base):
    """A configured rule; named *Row to stay distinct from the engine's ConstraintInstance."""

    __tablename__ = "constraint_instance"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    name: Mapped[str]
    template_key: Mapped[str]
    template_version: Mapped[int]
    params: Mapped[JsonDict] = mapped_column(JSONB)
    scope: Mapped[JsonDict] = mapped_column(JSONB)
    hard: Mapped[bool]
    weight: Mapped[int]
    enabled: Mapped[bool]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]
