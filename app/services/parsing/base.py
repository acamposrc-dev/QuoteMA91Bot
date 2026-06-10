"""Contratos de la capa de parsing.

Estrategia: codigo primero, LLM despues. Cada parser deterministico intenta
reconocer el documento; si ninguno lo reconoce, el dispatcher cae al parser
LLM (parser_fallback) que digiere cualquier formato nuevo.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


class UnrecognizedFormat(Exception):
    """El parser deterministico no reconoce este documento."""


@dataclass
class ParsedItem:
    name: str
    description: str | None = None
    quantity: int = 1
    preferred_brand: str | None = None
    specs: dict[str, str] = field(default_factory=dict)


@dataclass
class ParseResult:
    items: list[ParsedItem]
    method: str  # ParseMethod value


class DocumentParser(ABC):
    """Un parser deterministico. Debe ser barato de intentar."""

    method: str

    @abstractmethod
    def can_handle(self, filename: str, content: bytes) -> bool: ...

    @abstractmethod
    def parse(self, filename: str, content: bytes) -> ParseResult:
        """Lanza UnrecognizedFormat si el contenido no matchea la plantilla."""
