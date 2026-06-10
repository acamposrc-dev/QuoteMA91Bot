"""Loop agentico de busqueda por item.

Por cada tier (ve -> us -> cn -> global):

    queries iniciales (plantillas, sin LLM)
        |
        v
    +-> buscar en los providers del tier
    |       |
    |       v
    |   completar precios faltantes (extractor JSON-LD/meta/LLM)
    |       |
    |       v
    |   prefiltro de codigo -> matcher LLM (batch) -> opciones validas
    |       |
    |   suficientes opciones? --si--> siguiente tier o fin
    |       | no
    |       v
    +-- REFORMULAR: el LLM ve que se busco y que se rechazo (y por que),
        y propone queries nuevas. Maximo MAX_REFORMULATIONS_PER_TIER.

Presupuestos duros: max_searches_per_item corta el loop pase lo que pase.
El agente nunca inventa: si no llega a 4 opciones validas, el item queda
PARTIAL o NO_RESULTS y el reporte lo dice explicitamente.
"""

from dataclasses import dataclass, field

from pydantic import BaseModel, Field

from app.core.config import settings
from app.core.logging import get_logger
from app.db.session import SessionLocal
from app.models import QuoteItem, SearchLog
from app.services import currency, matcher
from app.services.extraction.price_extractor import extract_price
from app.services.llm import client as llm
from app.services.search.base import ProductCandidate
from app.services.search.registry import providers_for

log = get_logger(__name__)


# ---------------------------------------------------------------- queries

def initial_queries(item: QuoteItem) -> list[str]:
    """Plantillas deterministicas: cubren el caso comun sin gastar tokens."""
    queries: list[str] = [item.name]
    if item.preferred_brand:
        queries.append(f"{item.preferred_brand} {item.name}")
    main_specs = " ".join(list(item.specs.values())[:2]) if item.specs else ""
    if main_specs:
        queries.append(f"{item.name} {main_specs}")
    queries.append(f"comprar {item.name}")
    # dedup conservando orden
    seen: set[str] = set()
    return [q for q in queries if not (q.lower() in seen or seen.add(q.lower()))][:4]


class ReformulatedQueries(BaseModel):
    reasoning: str = Field(description="Diagnostico breve: por que fallaron las busquedas previas")
    queries: list[str] = Field(min_length=1, max_length=3, description="Queries nuevas, distintas a las previas")


def reformulate(
    item: QuoteItem,
    tried_queries: list[str],
    rejected: list[tuple[ProductCandidate, matcher.CandidateScore]],
) -> ReformulatedQueries:
    """El paso agentico: el LLM observa el fracaso y decide como buscar distinto."""
    rejected_text = "\n".join(
        f"- {c.title} -> {s.level}: {s.reason}" for c, s in rejected[:8]
    ) or "(no se encontro ningun candidato)"
    specs_text = "; ".join(f"{k}: {v}" for k, v in item.specs.items()) or "-"

    return llm.structured(
        role="query_reformulator",
        item_id=item.id,
        messages=[
            {
                "role": "system",
                "content": (
                    "Eres un experto en busqueda de productos. Las queries anteriores no "
                    "encontraron suficientes opciones validas. Analiza que fallo (termino "
                    "demasiado especifico, sinonimo regional faltante, nombre tecnico vs "
                    "comercial, ingles vs espanol) y propone hasta 3 queries NUEVAS. "
                    "Usa sinonimos, nombres alternativos del producto, o relaja specs no "
                    "criticas. Nunca repitas una query ya intentada."
                ),
            },
            {
                "role": "user",
                "content": (
                    f"Item: {item.name}\nDescripcion: {item.description or '-'}\n"
                    f"Specs: {specs_text}\n\n"
                    f"Queries ya intentadas: {tried_queries}\n\n"
                    f"Candidatos rechazados y motivo:\n{rejected_text}"
                ),
            },
        ],
        schema=ReformulatedQueries,
    )


# ---------------------------------------------------------------- agente

@dataclass
class AgentResult:
    valid: list[tuple[ProductCandidate, matcher.CandidateScore, float]] = field(default_factory=list)
    searches_used: int = 0


def _resolve_prices(candidates: list[ProductCandidate], item_id: str) -> list[ProductCandidate]:
    """Completa precio fetcheando la pagina cuando el provider solo dio la URL."""
    resolved: list[ProductCandidate] = []
    for c in candidates:
        if c.price_amount is not None:
            resolved.append(c)
            continue
        extracted = extract_price(c.url, item_id=item_id)
        if extracted.found and extracted.price_amount and extracted.in_stock is not False:
            c.price_amount = extracted.price_amount
            c.price_currency = extracted.price_currency
            c.seller = c.seller or extracted.seller
            resolved.append(c)
    return resolved


def run_search_agent(item: QuoteItem) -> AgentResult:
    result = AgentResult()
    needed = settings.options_per_item
    seen_urls: set[str] = set()

    with SessionLocal() as db:
        for tier in settings.tiers:
            if len(result.valid) >= needed or result.searches_used >= settings.max_searches_per_item:
                break

            providers = providers_for(tier)
            if not providers:
                continue

            tried: list[str] = []
            rejected: list[tuple[ProductCandidate, matcher.CandidateScore]] = []
            queries = initial_queries(item)
            iteration = 0

            while iteration <= settings.max_reformulations_per_tier:
                if len(result.valid) >= needed or result.searches_used >= settings.max_searches_per_item:
                    break

                # 1. BUSCAR
                candidates: list[ProductCandidate] = []
                for query in queries:
                    if result.searches_used >= settings.max_searches_per_item:
                        break
                    for provider in providers:
                        try:
                            found = provider.search(query, tier=tier)
                        except Exception as exc:
                            log.warning("provider_error", provider=provider.name, error=str(exc))
                            found = []
                        result.searches_used += 1
                        db.add(SearchLog(
                            item_id=item.id, tier=tier, provider=provider.name,
                            query=query, iteration=iteration, results_count=len(found),
                        ))
                        candidates.extend(c for c in found if c.url not in seen_urls)
                tried.extend(queries)
                db.commit()

                for c in candidates:
                    seen_urls.add(c.url)

                # 2. EVALUAR: precios -> prefiltro -> matcher batch
                candidates = _resolve_prices(candidates, item.id)
                candidates = matcher.prefilter(candidates, item.name)
                scored = matcher.score_candidates(
                    item.name, item.description, item.specs, candidates, item_id=item.id
                )

                for candidate, score in scored:
                    if score.score >= settings.equivalence_threshold:
                        usd = currency.to_usd(candidate.price_amount, candidate.price_currency)
                        if usd is not None:
                            result.valid.append((candidate, score, usd))
                    else:
                        rejected.append((candidate, score))

                log.info(
                    "agent_iteration_done", item=item.name, tier=tier, iteration=iteration,
                    valid_total=len(result.valid), searches=result.searches_used,
                )

                if len(result.valid) >= needed:
                    break

                # 3. REFORMULAR y volver a buscar
                iteration += 1
                if iteration > settings.max_reformulations_per_tier:
                    break
                try:
                    plan = reformulate(item, tried, rejected)
                except Exception as exc:
                    log.warning("reformulation_failed", error=str(exc))
                    break
                db.add(SearchLog(
                    item_id=item.id, tier=tier, provider="agent",
                    query=" | ".join(plan.queries), iteration=iteration,
                    results_count=0, reasoning=plan.reasoning,
                ))
                db.commit()
                queries = [q for q in plan.queries if q.lower() not in {t.lower() for t in tried}]
                if not queries:
                    break

    return result
