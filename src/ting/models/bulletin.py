from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import DateTime, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, utcnow


class Bulletin(Base):
    __tablename__ = "bulletins"

    bulletin_id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    posted_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), default=utcnow, nullable=False)
    posted_by: Mapped[str] = mapped_column(String(80), nullable=False)
