from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import DateTime, SmallInteger, Text, Uuid, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class Demand(Base):
    __tablename__ = "demand"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    slot_template_id: Mapped[UUID]
    name: Mapped[str]
    kind: Mapped[str]
    spec: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class Activity(Base):
    __tablename__ = "activity"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    demand_id: Mapped[UUID | None]
    series_id: Mapped[UUID | None]
    natural_key: Mapped[str | None]
    name: Mapped[str]
    duration_minutes: Mapped[int]
    candidate_starts: Mapped[list[datetime]] = mapped_column(ARRAY(DateTime(timezone=True)))
    attrs: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class Requirement(Base):
    __tablename__ = "requirement"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    activity_id: Mapped[UUID]
    position: Mapped[int] = mapped_column(SmallInteger)
    role: Mapped[str]
    resource_type_id: Mapped[UUID | None]
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    # Any: JSONB list of AttributePredicate dicts, validated on the way out.
    attr_predicates: Mapped[list[Any]] = mapped_column(JSONB)
    count_min: Mapped[int]
    count_max: Mapped[int]
    fixed_resource_ids: Mapped[list[UUID]] = mapped_column(ARRAY(Uuid[UUID]()))
    hard: Mapped[bool]
    weight: Mapped[int]


class Pin(Base):
    __tablename__ = "pin"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    activity_id: Mapped[UUID]
    start_at: Mapped[datetime | None]
    resources: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
