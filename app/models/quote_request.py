import enum
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer,  String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import ParseMethod, RequestSource, RequestStatus
from app.models.quote_item import QuoteItem
from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class QuoteRequest(Base):
    __tablename__ = 'quote_requests'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[RequestSource] = mapped_column(Enum(RequestSource))
    status: Mapped[RequestStatus] = mapped_column(Enum(RequestStatus), default=RequestStatus.RECEIVED, index=True)
    email_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    email_thread_id: Mapped[str | None] = mapped_column(String(255))
    reply_to: Mapped[str | None] = mapped_column(String(255))
    document_hash: Mapped[str | None] = mapped_column(String(64), index=True) 
    raw_document_path: Mapped[str | None] = mapped_column(String(512))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    parse_method: Mapped[ParseMethod] = mapped_column(Enum(ParseMethod))
    report_path: Mapped[str | None] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))

    # Relations
    items: Mapped[list['QuoteItem']] = relationship(back_populates='request', cascade='all, delete-orphan')
