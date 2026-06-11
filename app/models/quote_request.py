import enum
import uuid
from datetime import datetime

from sqlalchemy import JSON, DateTime, Enum, Float, ForeignKey, Integer, String, Text, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    pass


def _uuid() -> str:
    return str(uuid.uuid4())


class RequestSource(str, enum.Enum):
    EMAIL = "EMAIL"
    UPLOAD = "UPLOAD"


class RequestStatus(str, enum.Enum):
    RECEIVED = "RECEIVED"
    PARSING = "PARSING"
    PARSE_ERROR = "PARSE_ERROR"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"


class ItemStatus(str, enum.Enum):
    PENDING = "PENDING"
    SEARCHING = "SEARCHING"
    COMPLETED = "COMPLETED"        # 4 opciones validas
    PARTIAL = "PARTIAL"            # menos de 4 opciones validas
    NO_RESULTS = "NO_RESULTS"
    FAILED = "FAILED"


class ParseMethod(str, enum.Enum):
    TEMPLATE_XLSX = "TEMPLATE_XLSX"
    TEMPLATE_CSV = "TEMPLATE_CSV"
    EMAIL_TABLE = "EMAIL_TABLE"
    LLM_FALLBACK = "LLM_FALLBACK"


class QuoteRequest(Base):
    __tablename__ = "quote_requests"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    source: Mapped[RequestSource] = mapped_column(Enum(RequestSource))
    status: Mapped[RequestStatus] = mapped_column(
        Enum(RequestStatus), default=RequestStatus.RECEIVED, index=True
    )
    email_message_id: Mapped[str | None] = mapped_column(String(255), unique=True)
    email_thread_id: Mapped[str | None] = mapped_column(String(255))
    reply_to: Mapped[str | None] = mapped_column(String(255))
    document_hash: Mapped[str | None] = mapped_column(String(64), index=True)
    raw_document_path: Mapped[str | None] = mapped_column(String(512))
    original_filename: Mapped[str | None] = mapped_column(String(255))
    parse_method: Mapped[ParseMethod | None] = mapped_column(Enum(ParseMethod))
    report_path: Mapped[str | None] = mapped_column(String(512))
    error: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))

    items: Mapped[list["QuoteItem"]] = relationship(back_populates="request", cascade="all, delete-orphan")


class QuoteItem(Base):
    __tablename__ = "quote_items"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str] = mapped_column(ForeignKey("quote_requests.id"), index=True)
    name: Mapped[str] = mapped_column(String(512))
    description: Mapped[str | None] = mapped_column(Text)
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    preferred_brand: Mapped[str | None] = mapped_column(String(255))
    specs: Mapped[dict] = mapped_column(JSON, default=dict)
    status: Mapped[ItemStatus] = mapped_column(Enum(ItemStatus), default=ItemStatus.PENDING, index=True)
    searches_used: Mapped[int] = mapped_column(Integer, default=0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    request: Mapped[QuoteRequest] = relationship(back_populates="items")
    options: Mapped[list["ItemOption"]] = relationship(back_populates="item", cascade="all, delete-orphan")


class ItemOption(Base):
    __tablename__ = "item_options"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(ForeignKey("quote_items.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16))                 # ve | us | cn | global
    title: Mapped[str] = mapped_column(String(1024))
    seller: Mapped[str | None] = mapped_column(String(512))
    url: Mapped[str] = mapped_column(String(2048))
    price_amount: Mapped[float] = mapped_column(Float)
    price_currency: Mapped[str] = mapped_column(String(8))
    price_usd: Mapped[float] = mapped_column(Float, index=True)
    equivalence_score: Mapped[float] = mapped_column(Float)
    equivalence_level: Mapped[str] = mapped_column(String(16))    # exact|equivalent|partial|no_match
    equivalence_reason: Mapped[str | None] = mapped_column(Text)
    rank: Mapped[int | None] = mapped_column(Integer)             # 1-4 si quedo seleccionada
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    item: Mapped[QuoteItem] = relationship(back_populates="options")


class SearchLog(Base):
    __tablename__ = "search_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    item_id: Mapped[str] = mapped_column(ForeignKey("quote_items.id"), index=True)
    tier: Mapped[str] = mapped_column(String(16))
    provider: Mapped[str] = mapped_column(String(64))
    query: Mapped[str] = mapped_column(String(1024))
    iteration: Mapped[int] = mapped_column(Integer, default=0)    # 0 = inicial, 1+ = reformulaciones
    results_count: Mapped[int] = mapped_column(Integer, default=0)
    reasoning: Mapped[str | None] = mapped_column(Text)           # por que el agente reformulo
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class LLMLog(Base):
    __tablename__ = "llm_logs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=_uuid)
    request_id: Mapped[str | None] = mapped_column(String(36), index=True)
    item_id: Mapped[str | None] = mapped_column(String(36), index=True)
    role: Mapped[str] = mapped_column(String(32))
    model: Mapped[str] = mapped_column(String(128))
    tokens_in: Mapped[int] = mapped_column(Integer, default=0)
    tokens_out: Mapped[int] = mapped_column(Integer, default=0)
    cost_usd: Mapped[float] = mapped_column(Float, default=0.0)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
