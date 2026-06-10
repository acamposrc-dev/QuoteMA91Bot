"""Provider eBay Browse API (gratuita). Tier us / global."""

import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

from app.core.config import settings
from app.services.search.base import ProductCandidate, SearchProvider


class EbayProvider(SearchProvider):
    name = "ebay"
    needs_page_fetch = False

    @retry(stop=stop_after_attempt(3), wait=wait_exponential(min=1, max=10))
    def search(self, query: str, tier: str, max_results: int = 10) -> list[ProductCandidate]:
        if not settings.ebay_app_id:
            return []
        # Browse API requiere OAuth app token; aqui el flujo client_credentials
        token_resp = httpx.post(
            "https://api.ebay.com/identity/v1/oauth2/token",
            auth=(settings.ebay_app_id, settings.aliexpress_app_secret or ""),
            data={"grant_type": "client_credentials",
                  "scope": "https://api.ebay.com/oauth/api_scope"},
            timeout=20,
        )
        if token_resp.status_code != 200:
            return []
        token = token_resp.json()["access_token"]
        resp = httpx.get(
            "https://api.ebay.com/buy/browse/v1/item_summary/search",
            headers={"Authorization": f"Bearer {token}"},
            params={"q": query, "limit": max_results},
            timeout=20,
        )
        resp.raise_for_status()
        out: list[ProductCandidate] = []
        for it in resp.json().get("itemSummaries", []):
            price = it.get("price", {})
            out.append(
                ProductCandidate(
                    title=it.get("title", ""),
                    url=it.get("itemWebUrl", ""),
                    source=self.name,
                    tier=tier,
                    seller=(it.get("seller") or {}).get("username"),
                    price_amount=float(price["value"]) if price.get("value") else None,
                    price_currency=price.get("currency"),
                )
            )
        return out
