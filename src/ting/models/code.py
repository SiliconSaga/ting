from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Code(Base):
    __tablename__ = "codes"

    code_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code_str: Mapped[str] = mapped_column(String(40), unique=True, nullable=False, index=True)
    cohort_id: Mapped[UUID] = mapped_column(ForeignKey("cohorts.cohort_id"), nullable=False)
    printed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    first_used_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    advocate_grade: Mapped[int | None] = mapped_column(SmallInteger, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
