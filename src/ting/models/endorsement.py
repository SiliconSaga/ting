from datetime import datetime
from uuid import UUID

from sqlalchemy import DateTime, ForeignKey
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Endorsement(Base):
    __tablename__ = "endorsements"

    code_id: Mapped[UUID] = mapped_column(ForeignKey("codes.code_id"), primary_key=True)
    comment_id: Mapped[UUID] = mapped_column(ForeignKey("comments.comment_id"), primary_key=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
