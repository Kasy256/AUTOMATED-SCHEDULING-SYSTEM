from datetime import date
from uuid import UUID

from sqlalchemy.orm import Mapped, mapped_column

from cartlyf_api.db import Base


class FairnessLedgerRow(Base):
    __tablename__ = "fairness_ledger"

    organisation_id: Mapped[UUID] = mapped_column(primary_key=True)
    schedule_id: Mapped[UUID] = mapped_column(primary_key=True)
    version_id: Mapped[UUID]
    resource_id: Mapped[UUID] = mapped_column(primary_key=True)
    counter: Mapped[str] = mapped_column(primary_key=True)
    day: Mapped[date] = mapped_column(primary_key=True)
    count: Mapped[int]
