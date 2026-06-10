"""Matcher de equivalencias.

Pre-filtros deterministicos (codigo) reducen los candidatos; el LLM del rol
`matcher` puntua los supervivientes en UNA llamada batch por iteracion.
"""

import statistics
from typing import Literal

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.services.search.base import ProductCandidate

log = get_logger(__name__)


class CandidateScore(BaseModel):
    index: int = Field(description="Indice del candidato en la lista recibida")
    score: float = Field(ge=0.0, le=1.0)
    level: Literal["exact", "equivalent", "partial", "no_match"]
    reason: str = Field(description="Una frase: por que cumple o no las specs")


class MatchBatch(BaseModel):
    results: list[CandidateScore]


def prefilter(candidates: list[ProductCandidate], item_name: str) -> list[ProductCandidate]:
    """Filtros baratos antes de gastar tokens."""
    out = [c for c in candidates if c.title and c.url and c.price_amount and c.price_amount > 0]

    # descarta precios absurdos respecto a la mediana (10x arriba o abajo)
    prices = [c.price_amount for c in out if c.price_amount]
    if len(prices) >= 3:
        median = statistics.median(prices)
        out = [c for c in out if median / 10 <= c.price_amount <= median * 10]

    # al menos una palabra significativa del item en el titulo
    words = {w.lower() for w in item_name.split() if len(w) > 3}
    if words:
        out = [c for c in out if any(w in c.title.lower() for w in words)] or out

    return out[: settings.candidates_to_matcher]


def score_candidates(
    item_name: str,
    description: str | None,
    specs: dict,
    candidates: list[ProductCandidate],
    item_id: str | None = None,
) -> list[tuple[ProductCandidate, CandidateScore]]:
    """Una sola llamada LLM puntua todos los candidatos contra las specs."""
    if not candidates:
        return []

    from app.services.llm import client as llm

    listing = "\n".join(
        f"[{i}] {c.title} | precio: {c.price_amount} {c.price_currency or '?'} "
        f"| vendedor: {c.seller or '?'} | {c.snippet or ''}"
        for i, c in enumerate(candidates)
    )
    specs_text = "; ".join(f"{k}: {v}" for k, v in specs.items()) or "sin especificaciones"

    batch = llm.structured(
        role="matcher",
        item_id=item_id,
        messages=[
            {
                "role": "system",
                "content": (
                    "Evaluas si productos encontrados en la web satisfacen un item solicitado. "
                    "Niveles: exact (mismo producto/modelo), equivalent (cumple todas las specs "
                    "clave aunque sea otra marca), partial (cumple algunas), no_match. "
                    "Se estricto: en caso de duda baja el score. Devuelve un resultado por "
                    "candidato usando su indice."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Item solicitado: {item_name}\n"
                    f"Descripcion: {description or '-'}\n"
                    f"Especificaciones: {specs_text}\n\n"
                    f"Candidatos:\n{listing}"
                ),
            },
        ],
        schema=MatchBatch,
    )

    scored: list[tuple[ProductCandidate, CandidateScore]] = []
    for result in batch.results:
        if 0 <= result.index < len(candidates):
            scored.append((candidates[result.index], result))
    log.info(
        "match_batch_scored",
        item=item_name,
        candidates=len(candidates),
        valid=sum(1 for _, s in scored if s.score >= settings.equivalence_threshold),
    )
    return scored
