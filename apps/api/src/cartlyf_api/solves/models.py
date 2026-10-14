from datetime import datetime
from uuid import UUID

from sqlalchemy import Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class SolveRun(Base):
    __tablename__ = "solve_run"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    requested_by: Mapped[UUID]
    status: Mapped[str]
    problem: Mapped[JsonDict] = mapped_column(JSONB)
    problem_hash: Mapped[str]
    horizon_origin: Mapped[datetime]
    timezone: Mapped[str]
    progress: Mapped[JsonDict] = mapped_column(JSONB, server_default="{}")
    conflicts: Mapped[list[str]] = mapped_column(ARRAY(Text), server_default="{}")
    error: Mapped[str | None]
    version_id: Mapped[UUID | None]
    cancel_requested_at: Mapped[datetime | None]
    heartbeat_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    started_at: Mapped[datetime | None]
    finished_at: Mapped[datetime | None]
