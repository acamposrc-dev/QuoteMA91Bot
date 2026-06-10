from datetime import datetime
from pydantic import BaseModel, ConfigDict


class OptionOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    rank: int | None
    tier: str | None
    title: str | None
    seller: str | None
    url: str
    price_amount: float
    price_currency: str
    price_usd: float
    equivalence_score: float
    equivalence_level: str
    equivalence_reason: str | None



class ItemOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    name: str
    description: str | None
    quantity: int
    status: str
    searches_used: int
    options: list[OptionOut] = []



class RequestOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: str
    source: str
    status: str
    parse_method: str | None
    original_filename: str | None
    error: str | None
    created_at: datetime
    completed_at: datetime | None
    items: list[ItemOut] = []


class RequestCreated(BaseModel):
    id: str
    status: str