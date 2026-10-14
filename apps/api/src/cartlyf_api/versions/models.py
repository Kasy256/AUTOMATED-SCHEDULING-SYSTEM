from datetime import datetime
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class SolutionVersion(Base):
    __tablename__ = "solution_version"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    schedule_id: Mapped[UUID]
    solve_run_id: Mapped[UUID]
    parent_version_id: Mapped[UUID | None]
    number: Mapped[int]
    status: Mapped[str]
    solver_status: Mapped[str]
    score: Mapped[JsonDict] = mapped_column(JSONB)
    checker_report: Mapped[JsonDict] = mapped_column(JSONB)
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    published_at: Mapped[datetime | None]
    published_by: Mapped[UUID | None]
    archived_at: Mapped[datetime | None]


class Assignment(Base):
    __tablename__ = "assignment"

    organisation_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(primary_key=True)
    start_at: Mapped[datetime]
    end_at: Mapped[datetime]


class AssignmentResource(Base):
    __tablename__ = "assignment_resource"

    organisation_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID] = mapped_column(primary_key=True)
    activity_id: Mapped[UUID] = mapped_column(primary_key=True)
    role: Mapped[str] = mapped_column(primary_key=True)
    resource_id: Mapped[UUID] = mapped_column(primary_key=True)
