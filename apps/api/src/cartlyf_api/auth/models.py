from datetime import datetime
from uuid import UUID

from sqlalchemy import LargeBinary, func, text
from sqlalchemy.dialects.postgresql import CITEXT
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class AppUser(Base):
    __tablename__ = "app_user"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(CITEXT)
    name: Mapped[str]
    password_hash: Mapped[str | None]
    email_verified: Mapped[bool] = mapped_column(server_default=text("false"))
    # Read-only to the app: the column grant excludes it; set by operators in SQL.
    is_platform_admin: Mapped[bool] = mapped_column(server_default=text("false"))
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
    deleted_at: Mapped[datetime | None]


class RefreshToken(Base):
    __tablename__ = "refresh_token"

    id: Mapped[UUID] = mapped_column(primary_key=True)
    user_id: Mapped[UUID]
    family_id: Mapped[UUID]
    token_hash: Mapped[bytes] = mapped_column(LargeBinary)
    active_organisation_id: Mapped[UUID | None]
    expires_at: Mapped[datetime]
    used_at: Mapped[datetime | None]
    revoked_at: Mapped[datetime | None]
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
