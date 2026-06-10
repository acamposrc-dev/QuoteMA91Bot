"""Normalizacion de monedas a USD. Tasa BCV para VES, exchangerate.host para el resto.
Cachea en Redis por 6 horas."""

import json

import httpx
import redis

from app.core.config import settings
from app.core.logging import get_logger

log = get_logger(__name__)
_redis = redis.Redis.from_url(settings.redis_url, decode_responses=True)
TTL = 6 * 3600


def _cached(key: str, fetch) -> float | None:
    raw = _redis.get(key)
    if raw is not None:
        return json.loads(raw)
    value = fetch()
    if value is not None:
        _redis.setex(key, TTL, json.dumps(value))
    return value


def _bcv_rate() -> float | None:
    """Bolivares por USD segun tasa oficial BCV (via pydolarve)."""
    try:
        resp = httpx.get("https://pydolarve.org/api/v2/tipo-cambio", params={"currency": "usd"}, timeout=15)
        if resp.status_code == 200:
            return float(resp.json().get("price"))
    except (httpx.HTTPError, ValueError, TypeError):
        pass
    return None


def _fx_rate(currency: str) -> float | None:
    """Unidades de `currency` por 1 USD."""
    try:
        resp = httpx.get("https://api.exchangerate.host/latest",
                         params={"base": "USD", "symbols": currency}, timeout=15)
        if resp.status_code == 200:
            return float(resp.json()["rates"][currency])
    except (httpx.HTTPError, KeyError, ValueError, TypeError):
        pass
    return None


def to_usd(amount: float, currency: str | None) -> float | None:
    cur = (currency or "USD").upper()
    if cur in ("USD", "US$", "REF"):
        return round(amount, 2)
    if cur in ("VES", "BS", "BS.", "VED"):
        rate = _cached("fx:VES", _bcv_rate)
    else:
        rate = _cached(f"fx:{cur}", lambda: _fx_rate(cur))
    if not rate:
        log.warning("fx_rate_unavailable", currency=cur)
        return None
    return round(amount / rate, 2)
