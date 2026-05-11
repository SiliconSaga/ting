from datetime import datetime
from uuid import UUID, uuid4
from sqlalchemy import DateTime, Integer, String, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column
from .base import Base, utcnow


class MetricsEvent(Base):
    __tablename__ = "metrics_events"

    event_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    event: Mapped[str] = mapped_column(String(40), nullable=False)
    code_id: Mapped[UUID | None] = mapped_column(ForeignKey("codes.code_id"), nullable=True)
    duration_seconds: Mapped[int | None] = mapped_column(Integer, nullable=True)
    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
