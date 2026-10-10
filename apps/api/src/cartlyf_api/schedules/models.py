from datetime import date, datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict
from cartlyf_api.schedules.time_grid import Horizon, horizon_for


class Schedule(Base):
    __tablename__ = "schedule"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    name: Mapped[str]
    timezone: Mapped[str]
    start_date: Mapped[date]
    end_date: Mapped[date]
    day_parts: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]

    def horizon(self) -> Horizon:
        return horizon_for(self.start_date, self.end_date, self.timezone)


class SlotTemplate(Base):
    __tablename__ = "slot_template"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    name: Mapped[str]
    definition: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
