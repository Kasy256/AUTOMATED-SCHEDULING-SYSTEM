from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class Organisation(Base):
    __tablename__ = "organisation"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    name: Mapped[str]
    timezone: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class Membership(Base):
    __tablename__ = "membership"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    user_id: Mapped[UUID]
    status: Mapped[str]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class MembershipRole(Base):
    __tablename__ = "membership_role"

    organisation_id: Mapped[UUID] = mapped_column(primary_key=True)
    membership_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(primary_key=True)
