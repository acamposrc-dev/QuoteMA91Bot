"""Ranking final: ordena por (prioridad de tier, precio USD) y toma el top N."""

from app.core.config import settings
from app.models import ItemOption
from app.services.matcher import CandidateScore
from app.services.search.base import ProductCandidate


def rank_and_build_options(
    item_id: str,
    valid: list[tuple[ProductCandidate, CandidateScore, float]],
) -> list[ItemOption]:
    tier_priority = {t: i for i, t in enumerate(settings.tiers)}
    ordered = sorted(valid, key=lambda v: (tier_priority.get(v[0].tier, 99), v[2]))

    options: list[ItemOption] = []
    seen_urls: set[str] = set()
    for candidate, score, usd in ordered:
        if candidate.url in seen_urls:
            continue
        seen_urls.add(candidate.url)
        options.append(ItemOption(
            item_id=item_id,
            tier=candidate.tier,
            title=candidate.title[:1024],
            seller=candidate.seller,
            url=candidate.url[:2048],
            price_amount=candidate.price_amount,
            price_currency=(candidate.price_currency or "USD").upper(),
            price_usd=usd,
            equivalence_score=score.score,
            equivalence_level=score.level,
            equivalence_reason=score.reason,
        ))
        if len(options) == settings.options_per_item:
            break

    for i, opt in enumerate(options, start=1):
        opt.rank = i
    return options
