from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class SummarySnapshot(Base):
    __tablename__ = "summary_snapshots"
    __table_args__ = (UniqueConstraint("cohort_id", "survey_id", "captured_at"),)

    snapshot_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    cohort_id: Mapped[UUID] = mapped_column(ForeignKey("cohorts.cohort_id"), nullable=False)
    survey_id: Mapped[UUID] = mapped_column(ForeignKey("surveys.survey_id"), nullable=False)
    captured_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
