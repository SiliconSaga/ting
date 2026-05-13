from datetime import datetime
from decimal import Decimal
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey, Numeric
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Pledge(Base):
    __tablename__ = "pledges"

    code_id: Mapped[UUID] = mapped_column(ForeignKey("codes.code_id"), primary_key=True)
    proposal_id: Mapped[UUID] = mapped_column(ForeignKey("proposals.proposal_id"), primary_key=True)
    amount_dollars: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False, default=0)
    hours_per_week: Mapped[Decimal] = mapped_column(Numeric(6, 2), nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False,
    )
