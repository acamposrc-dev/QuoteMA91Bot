from app.services.matcher import prefilter
from app.services.search.base import ProductCandidate


def _c(title, price):
    return ProductCandidate(title=title, url=f"https://x.com/{title}", source="t",
                            tier="us", price_amount=price, price_currency="USD")


def test_prefilter_drops_absurd_prices_and_unrelated_titles():
    cands = [
        _c("Taladro percutor Bosch 750W", 89.0),
        _c("Taladro percutor DeWalt 800W", 95.0),
        _c("Taladro Makita 700W", 110.0),
        _c("Taladro juguete", 2.0),            # 10x debajo de la mediana
        _c("Licuadora Oster", 90.0),           # titulo no relacionado
    ]
    out = prefilter(cands, "Taladro percutor")
    titles = [c.title for c in out]
    assert "Taladro juguete" not in titles
    assert "Licuadora Oster" not in titles
    assert len(out) == 3
