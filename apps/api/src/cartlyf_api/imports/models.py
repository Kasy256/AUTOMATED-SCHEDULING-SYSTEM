from datetime import datetime
from typing import Any
from uuid import UUID

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class ImportJob(Base):
    __tablename__ = "import_job"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    organisation_id: Mapped[UUID]
    kind: Mapped[str]
    status: Mapped[str]
    resource_type_id: Mapped[UUID | None]
    schedule_id: Mapped[UUID | None]
    filename: Mapped[str]
    object_key: Mapped[str | None]
    size_bytes: Mapped[int | None]
    content_sha256: Mapped[str | None]
    # Any: JSONB list of column names.
    columns: Mapped[list[Any] | None] = mapped_column(JSONB)
    mapping: Mapped[JsonDict | None] = mapped_column(JSONB)
    report: Mapped[JsonDict | None] = mapped_column(JSONB)
    created_by: Mapped[UUID]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(server_default=func.now())
    committed_at: Mapped[datetime | None]
