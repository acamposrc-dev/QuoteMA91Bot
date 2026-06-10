"""Extraccion de precio desde paginas de producto (tier Venezuela, principalmente).

Orden de intentos (barato -> caro):
  1. JSON-LD schema.org Product (WooCommerce/Shopify casi siempre lo publican)
  2. Meta tags (og:price:amount, product:price) y atributos itemprop
  3. LLM (rol extractor_fallback) con el HTML reducido a texto
"""

import json
import re

import httpx
from pydantic import BaseModel
from selectolax.parser import HTMLParser

from app.core.logging import get_logger
from app.services.llm import client as llm

log = get_logger(__name__)

UA = "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124 Safari/537.36"
PRICE_RE = re.compile(r"(?:bs\.?|ref|usd|\$)\s*([\d.,]+)", re.IGNORECASE)


class ExtractedPrice(BaseModel):
    found: bool
    price_amount: float | None = None
    price_currency: str | None = None   # USD | VES | EUR | CNY ...
    in_stock: bool | None = None
    seller: str | None = None


def fetch_html(url: str) -> str | None:
    try:
        resp = httpx.get(url, headers={"User-Agent": UA}, timeout=15, follow_redirects=True)
        if resp.status_code == 200 and "text/html" in resp.headers.get("content-type", ""):
            return resp.text
    except httpx.HTTPError as exc:
        log.info("fetch_failed", url=url, error=str(exc))
    return None


def _normalize_number(raw: str) -> float | None:
    raw = raw.strip()
    if "," in raw and "." in raw:
        raw = raw.replace(".", "").replace(",", ".") if raw.rfind(",") > raw.rfind(".") else raw.replace(",", "")
    elif "," in raw:
        raw = raw.replace(",", ".") if len(raw.split(",")[-1]) == 2 else raw.replace(",", "")
    try:
        return float(raw)
    except ValueError:
        return None


def _from_jsonld(tree: HTMLParser) -> ExtractedPrice | None:
    for node in tree.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except (json.JSONDecodeError, TypeError):
            continue
        blocks = data if isinstance(data, list) else [data]
        for block in blocks:
            if not isinstance(block, dict):
                continue
            graph = block.get("@graph", [block])
            for obj in graph:
                if not isinstance(obj, dict) or obj.get("@type") not in ("Product", ["Product"]):
                    continue
                offers = obj.get("offers") or {}
                if isinstance(offers, list):
                    offers = offers[0] if offers else {}
                price = offers.get("price") or offers.get("lowPrice")
                if price is None:
                    continue
                amount = _normalize_number(str(price))
                if amount is None:
                    continue
                availability = str(offers.get("availability", ""))
                return ExtractedPrice(
                    found=True,
                    price_amount=amount,
                    price_currency=(offers.get("priceCurrency") or "USD").upper(),
                    in_stock=("InStock" in availability) if availability else None,
                    seller=(obj.get("brand") or {}).get("name") if isinstance(obj.get("brand"), dict) else None,
                )
    return None


def _from_meta(tree: HTMLParser) -> ExtractedPrice | None:
    selectors = [
        ('meta[property="product:price:amount"]', 'meta[property="product:price:currency"]'),
        ('meta[property="og:price:amount"]', 'meta[property="og:price:currency"]'),
    ]
    for amount_sel, currency_sel in selectors:
        node = tree.css_first(amount_sel)
        if node is None:
            continue
        amount = _normalize_number(node.attributes.get("content", ""))
        if amount is None:
            continue
        cur_node = tree.css_first(currency_sel)
        currency = (cur_node.attributes.get("content") if cur_node else None) or "USD"
        return ExtractedPrice(found=True, price_amount=amount, price_currency=currency.upper())
    node = tree.css_first('[itemprop="price"]')
    if node is not None:
        amount = _normalize_number(node.attributes.get("content") or node.text() or "")
        if amount is not None:
            cur = tree.css_first('[itemprop="priceCurrency"]')
            currency = (cur.attributes.get("content") if cur else None) or "USD"
            return ExtractedPrice(found=True, price_amount=amount, price_currency=currency.upper())
    return None


def _from_llm(tree: HTMLParser, url: str, item_id: str | None) -> ExtractedPrice:
    for tag in ("script", "style", "nav", "footer", "svg", "noscript"):
        for node in tree.css(tag):
            node.decompose()
    text = re.sub(r"\s+", " ", tree.body.text() if tree.body else "")[:12_000]
    return llm.structured(
        role="extractor_fallback",
        item_id=item_id,
        messages=[
            {
                "role": "system",
                "content": (
                    "Extraes el precio de venta de una pagina de producto. Devuelve found=false "
                    "si la pagina no es una pagina de producto con precio claro. Moneda: VES si "
                    "el precio esta en bolivares (Bs), USD si esta en dolares o '$' o 'REF'."
                ),
            },
            {"role": "user", "content": f"URL: {url}\n\nTexto de la pagina:\n{text}"},
        ],
        schema=ExtractedPrice,
    )


def extract_price(url: str, item_id: str | None = None) -> ExtractedPrice:
    html = fetch_html(url)
    if html is None:
        return ExtractedPrice(found=False)
    tree = HTMLParser(html)

    result = _from_jsonld(tree)
    if result:
        log.info("price_via_jsonld", url=url)
        return result
    result = _from_meta(tree)
    if result:
        log.info("price_via_meta", url=url)
        return result
    log.info("price_via_llm_fallback", url=url)
    return _from_llm(tree, url, item_id)
