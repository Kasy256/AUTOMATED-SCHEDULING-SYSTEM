from datetime import datetime

from sqlalchemy import func
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base, JsonDict


class IndustryTemplate(Base):
    """Global (not tenant-scoped) reference data; the app role can only read it."""

    __tablename__ = "industry_template"

    key: Mapped[str] = mapped_column(primary_key=True)
    version: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str]
    definition: Mapped[JsonDict] = mapped_column(JSONB)
    created_at: Mapped[datetime] = mapped_column(server_default=func.now())
