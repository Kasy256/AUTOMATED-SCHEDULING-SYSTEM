from datetime import datetime
from uuid import UUID

from sqlalchemy import SmallInteger, Text, func
from sqlalchemy.dialects.postgresql import ARRAY, JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class ResourceType(Base):
    __tablename__ = "resource_type"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    key: Mapped[str]
    name: Mapped[str]
    kind: Mapped[str]
    attribute_schema: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class Resource(Base):
    __tablename__ = "resource"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    resource_type_id: Mapped[UUID]
    code: Mapped[str]
    name: Mapped[str]
    tags: Mapped[list[str]] = mapped_column(ARRAY(Text))
    attributes: Mapped[JsonDict] = mapped_column(JSONB)
    capacity: Mapped[int | None]
    size: Mapped[int | None]
    concurrency: Mapped[int]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class AvailabilityRule(Base):
    __tablename__ = "availability_rule"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    kind: Mapped[str]
    weekday: Mapped[int] = mapped_column(SmallInteger)
    start_minute: Mapped[int] = mapped_column(SmallInteger)
    end_minute: Mapped[int] = mapped_column(SmallInteger)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())


class AvailabilityException(Base):
    __tablename__ = "availability_exception"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    resource_id: Mapped[UUID]
    kind: Mapped[str]
    starts_at: Mapped[datetime]
    ends_at: Mapped[datetime]
    reason: Mapped[str | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
