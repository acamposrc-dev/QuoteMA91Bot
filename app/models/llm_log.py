import enum
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer,  String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import ItemStatus, ParseMethod, RequestSource, RequestStatus
from app.models.quote_item import QuoteItem
from app.models.quote_request import QuoteRequest
from app.db.base import Base


def _uuid() -> str:
    return str(uuid.uuid4())



class LLMLog(Base): 
    __tablename__ = 'llm_logs'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str | None] = mapped_column(String(36), index = True)
    item_id: Mapped[str | None] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

