from datetime import datetime, timezone
from sqlalchemy import Column, Integer, String, Text, DateTime
from .database import Base


def _utcnow():
    return datetime.now(timezone.utc)


class Ticket(Base):
    __tablename__ = "tickets"

    id = Column(Integer, primary_key=True, index=True)
    ticket_id = Column(String, unique=True, index=True, nullable=False)
    request_text = Column(Text, nullable=False)
    category = Column(String, nullable=False)
    priority = Column(String, nullable=False)
    assigned_team = Column(String, nullable=False)
    summary = Column(Text, nullable=False)
    status = Column(String, nullable=False, default="open")
    created_at = Column(DateTime, default=_utcnow)
    updated_at = Column(DateTime, default=_utcnow, onupdate=_utcnow)
