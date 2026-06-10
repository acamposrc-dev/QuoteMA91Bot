import enum
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer,  String, Text, func
from sqlalchemy.orm import  Mapped, mapped_column, relationship
from app.models.enums import ParseMethod, RequestSource, RequestStatus
from app.models.quote_item import QuoteItem
from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(ForeignKey("quote_items.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(64))
    query: Mapped[str] = mapped_column(String(1024))
    iteration: Mapped[int] = mapped_column(Integer, default=0)
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    


