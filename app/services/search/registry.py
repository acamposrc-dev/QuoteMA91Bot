"""Mapeo tier -> providers. Agregar una tienda nueva = agregar un provider aqui."""

from app.services.search.base import SearchProvider
from app.services.search.ebay import EbayProvider
from app.services.search.serper import SerperShoppingProvider, SerperWebVenezuelaProvider

_shopping = SerperShoppingProvider()
_ve_web = SerperWebVenezuelaProvider()
_ebay = EbayProvider()

TIER_PROVIDERS: dict[str, list[SearchProvider]] = {
    "ve": [_ve_web],
    "us": [_shopping, _ebay],
    "cn": [_shopping],          # TODO: AliExpressProvider con app key/secret
    "global": [_shopping, _ebay],
}


def providers_for(tier: str) -> list[SearchProvider]:
    return TIER_PROVIDERS.get(tier, [])
