from datetime import datetime
from uuid import UUID

from sqlalchemy import BigInteger, Identity, func, text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(BigInteger, Identity(), primary_key=True)
    organisation_id: Mapped[UUID]
    actor_user_id: Mapped[UUID | None]
    action: Mapped[str]
    target_type: Mapped[str | None]
    target_id: Mapped[UUID | None]
    details: Mapped[dict[str, object]] = mapped_column(JSONB, server_default=text("'{}'"))
    via_platform_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
