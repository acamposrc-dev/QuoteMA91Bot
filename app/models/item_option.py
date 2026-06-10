import enum
import uuid
from datetime import datetime
from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer,  String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship
from app.models.enums import ItemStatus, ParseMethod, RequestSource, RequestStatus
from app.models.quote_item import QuoteItem
from app.db.base import Base

def _uuid() -> str:
    return str(uuid.uuid4())




class ItemOption(Base):
    __tablename__ = 'item_options'

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(ForeignKey('quote_items.id'), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    title: Mapped[str] = mapped_column(String(1024))
    seller: Mapped[str | None] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(2048))
    price_amount: Mapped[float] = mapped_column(Float)
    price_currency: Mapped[str] = mapped_column(String(8))
    price_usd: Mapped[float] = mapped_column(Float)
    equivalence_score: Mapped[float] = mapped_column(Float)
    equivalence_level: Mapped[str] = mapped_column(String(16))
    equivalence_reason: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)
    
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[QuoteItem] = relationship(back_populates='options')

