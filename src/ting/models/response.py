from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Response(Base):
    __tablename__ = "responses"
    __table_args__ = (UniqueConstraint("code_id", "question_id", name="uq_response_code_question"),)

    response_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    code_id: Mapped[UUID] = mapped_column(ForeignKey("codes.code_id"), nullable=False)
    question_id: Mapped[UUID] = mapped_column(ForeignKey("questions.question_id"), nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utcnow, onupdate=utcnow, nullable=False,
    )
