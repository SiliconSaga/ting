from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import String, DateTime, Text
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, utcnow


class Cohort(Base):
    __tablename__ = "cohorts"

    cohort_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(120), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    retired_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
