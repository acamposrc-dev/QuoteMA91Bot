from abc import ABC, abstractmethod
from dataclasses import dataclass


@dataclass
class ProductCandidate:
    title: str
    url: str
    source: str                       # provider que lo encontro
    tier: str
    seller: str | None = None
    price_amount: float | None = None # None => hay que fetchear la pagina
    price_currency: str | None = None
    snippet: str | None = None


class SearchProvider(ABC):
    name: str
    needs_page_fetch: bool = False    # True si el provider devuelve URLs sin precio

    @abstractmethod
    def search(self, query: str, tier: str, max_results: int = 10) -> list[ProductCandidate]: ...
