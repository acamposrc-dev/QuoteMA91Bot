import enum
from typing import TYPE_CHECKING
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer,  String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import ItemStatus, ParseMethod, RequestSource, RequestStatus
from app.db.base import Base

if TYPE_CHECKING:
    from app.models.item_option import ItemOption
    from app.models.quote_request import QuoteRequest

def _uuid() -> str:
    return str(uuid.uuid4())



class QuoteItem(Base): 
    __tablename__ = 'quote_items'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default= _uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey('quote_requests.id'), index=True)
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    preferred_brand: Mapped[str | None] = mapped_column(String(255))
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.PENDING, index=True)
    searches_used: Mapped[int] = mapped_column(Integer, default=0)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    request: Mapped["QuoteRequest"] = relationship(back_populates="items")
    options: Mapped[list['ItemOption']] = relationship(back_populates='item', cascade="all, delete-orphan")
