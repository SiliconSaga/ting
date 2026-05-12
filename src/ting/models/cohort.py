from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Text, SmallInteger, ForeignKey, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, utcnow


class Cohort(Base):
    __tablename__ = "cohorts"
    __table_args__ = (UniqueConstraint("school_code", "batch_number", name="uq_cohort_school_batch"),)

    cohort_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    school_code: Mapped[str] = mapped_column(String(3), ForeignKey("schools.school_code"), nullable=False)
    batch_number: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    expires_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
