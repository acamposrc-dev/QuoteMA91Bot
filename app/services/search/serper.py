"""Provider Serper (google.serper.dev).

Dos modos:
  - shopping: resultados de Google Shopping con precio estructurado (us / global)
  - web:      busqueda organica; para el tier 've' restringe a dominios .com.ve
              y devuelve URLs que luego pasan por el extractor de precios.
"""

import re

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.core.logging import get_logger
from app.services.search.base import ProductCandidate, SearchProvider

log = get_logger(__name__)

PRICE_RE = re.compile(r"[\$]?\s*([\d.,]+)")

TIER_PARAMS = {
    "ve": {"gl": "ve", "hl": "es"},
    "us": {"gl": "us", "hl": "en"},
    "global": {"gl": "us", "hl": "en"},
}


def _parse_price(raw: str | None) -> tuple[float | None, str | None]:
    if not raw:
        return None, None
    currency = "USD" if "$" in raw else None
    if "bs" in raw.lower():
        currency = "VES"
    m = PRICE_RE.search(raw.replace("\u00a0", " "))
    if not m:
        return None, currency
    num = m.group(1)
    # normaliza 1.234,56 / 1,234.56
    if "," in num and "." in num:
        num = num.replace(".", "").replace(",", ".") if num.rfind(",") > num.rfind(".") else num.replace(",", "")
    elif "," in num:
        num = num.replace(",", ".") if len(num.split(",")[-1]) == 2 else num.replace(",", "")
    try:
        return float(num), currency
    except ValueError:
        return None, currency


class SerperShoppingProvider(SearchProvider):
    name = "serper_shopping"
    needs_page_fetch = False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def search(self, query: str, tier: str, max_results: int = 10) -> list[ProductCandidate]:
        params = TIER_PARAMS.get(tier, TIER_PARAMS["global"])
        resp = httpx.post(
            "https://google.serper.dev/shopping",
            headers={"X-API-KEY": settings.serper_api_key},
            json={"q": query, **params, "num": max_results},
            timeout=20,
        )
        resp.raise_for_status()
        out: list[ProductCandidate] = []
        for r in resp.json().get("shopping", [])[:max_results]:
            amount, currency = _parse_price(r.get("price"))
            out.append(
                ProductCandidate(
                    title=r.get("title", ""),
                    url=r.get("link", ""),
                    source=self.name,
                    tier=tier,
                    seller=r.get("source"),
                    price_amount=amount,
                    price_currency=currency or ("USD" if tier in ("us", "global") else None),
                )
            )
        return out


class SerperWebVenezuelaProvider(SearchProvider):
    """Busqueda organica restringida a tiendas venezolanas (.com.ve).

    Devuelve URLs sin precio confiable -> el agente las pasa por el extractor.
    """

    name = "serper_web_ve"
    needs_page_fetch = True

    EXCLUDE = ("facebook.com", "instagram.com", "youtube.com", "wikipedia.org")

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def search(self, query: str, tier: str, max_results: int = 10) -> list[ProductCandidate]:
        resp = httpx.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": settings.serper_api_key},
            json={"q": f"{query} site:.com.ve", "gl": "ve", "hl": "es", "num": max_results},
            timeout=20,
        )
        resp.raise_for_status()
        out: list[ProductCandidate] = []
        for r in resp.json().get("organic", []):
            url = r.get("link", "")
            if any(d in url for d in self.EXCLUDE):
                continue
            out.append(
                ProductCandidate(
                    title=r.get("title", ""),
                    url=url,
                    source=self.name,
                    tier=tier,
                    snippet=r.get("snippet"),
                )
            )
        return out[:max_results]
