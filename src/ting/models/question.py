from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow

QUESTION_TYPES = ("ranking", "nps", "likert")


class Question(Base):
    __tablename__ = "questions"
    __table_args__ = (
        # Belt-and-suspenders with the loader-side validator: refuse to write
        # a row with an unknown type at the DB layer too.
        CheckConstraint(
            f"type IN ({', '.join(repr(t) for t in QUESTION_TYPES)})",
            name="ck_questions_type",
        ),
    )

    question_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    slug: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    type: Mapped[str] = mapped_column(String(20), nullable=False)  # ranking | nps | likert
    prompt: Mapped[str] = mapped_column(Text, nullable=False)
    payload: Mapped[dict] = mapped_column(JSONB, nullable=False, default=dict)
    display_order: Mapped[int | None] = mapped_column(Integer, nullable=True)
    survey_id: Mapped[UUID] = mapped_column(
        ForeignKey("surveys.survey_id"), nullable=False, index=True,
    )
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
