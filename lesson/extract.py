"""Checkpoint 2: read explicit page data; never guess missing commerce fields."""

import json
import re
from datetime import datetime, timezone

from bs4 import BeautifulSoup

from lesson.pages import check_page, clean_url, identify_product


def schema_type(node, name):
    value = node.get("@type", [])
    values = [value] if isinstance(value, str) else value
    return isinstance(values, list) and any(
        isinstance(item, str) and item.rsplit("/", 1)[-1] == name for item in values
    )


def product_nodes(value):
    """Walk only top-level JSON-LD, @graph and mainEntity, not recommendations."""
    if isinstance(value, list):
        for item in value:
            yield from product_nodes(item)
    elif isinstance(value, dict):
        if schema_type(value, "Product"):
            yield value
        else:
            yield from product_nodes(value.get("@graph"))
            yield from product_nodes(value.get("mainEntity"))


def main_product(soup, url):
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            products.extend(product_nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    identity = identify_product(url)
    matches = []
    for product in products:
        reference = product.get("url") or product.get("@id")
        if isinstance(reference, str):
            try:
                if identify_product(reference) == identity:
                    matches.append(product)
            except ValueError:
                pass
    if len(matches) == 1:
        return matches[0]
    if len(products) == 1 and not (products[0].get("url") or products[0].get("@id")):
        return products[0]
    if products:
        raise ValueError("Cannot safely identify one main Product in the page JSON-LD.")
    return None


def text(soup, selector):
    tag = soup.select_one(selector)
    return tag.get_text(" ", strip=True) if tag else None


def meta(soup, field):
    tag = soup.select_one(f'meta[property="product:{field}"], [itemprop="{field}"]')
    return tag.get("content") if tag else None


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    # Refuse a different selected product (for example an Amazon variant change).
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get("href"):
        if identify_product(canonical["href"]) != (retailer, product_id):
            raise ValueError("Page canonical URL identifies a different product.")
    if retailer == "amazon":
        asin = soup.select_one('input#ASIN')
        if asin and asin.get("value") and asin["value"] != product_id:
            raise ValueError("Amazon selected a different ASIN; use that product's exact URL.")
    record = {
        "retailer": retailer, "product_id": product_id, "product_url": url,
        "title": None, "price": None, "currency": None, "availability": None,
        "seller": None, "discount": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "html",
    }
    product = main_product(soup, url)
    if product:
        record["extraction_method"] = "json-ld"
        record["title"] = product.get("name")
        offers = product.get("offers")
        if isinstance(offers, list) and len(offers) == 1:
            offers = offers[0]
        # A range/aggregate or multiple sellers is not one exact price.
        if not isinstance(offers, dict) or not schema_type(offers, "Offer"):
            raise ValueError("Expected one exact Offer; price ranges/multiple offers are rejected.")
        if offers.get("url"):
            if not isinstance(offers["url"], str) or identify_product(offers["url"]) != (retailer, product_id):
                raise ValueError("Offer belongs to a different product; no price collected.")
        record["price"] = offers.get("price")
        record["currency"] = offers.get("priceCurrency")
        record["availability"] = offers.get("availability")
        seller = offers.get("seller")
        record["seller"] = seller.get("name") if isinstance(seller, dict) else None
        return record

    # These fallbacks only inspect the main product's named HTML elements.
    # No whole-page price regex: it could pick a monthly payment or accessory.
    titles = {
        "amazon": "#productTitle", "bestbuy": "h1",
        "target": 'h1[data-test="product-title"], h1',
        "walmart": 'h1[itemprop="name"], h1',
    }
    record["title"] = text(soup, titles[retailer])
    record["price"] = meta(soup, "price:amount") or meta(soup, "price")
    record["currency"] = meta(soup, "price:currency") or meta(soup, "priceCurrency")
    record["availability"] = meta(soup, "availability")
    price_selectors = {
        "bestbuy": '[data-testid="customer-price"]',
        "target": '[data-test="product-price"]',
        "walmart": '[itemprop="price"]',
    }
    if retailer in price_selectors and record["price"] is None:
        displayed = text(soup, price_selectors[retailer])
        # Match only a single whole price in the named main-product price element.
        if displayed and re.fullmatch(r"(?:US\$|\$)?[\d,]+\.\d{2}", displayed):
            record["price"] = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            if displayed.startswith("US$"):
                record["currency"] = "USD"
    if retailer == "amazon":
        container = soup.select_one("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div")
        if container and record["price"] is None:
            displayed = text(container, ".a-price:not(.a-text-price) .a-offscreen")
            if displayed:
                # US$ explicitly identifies currency; a bare $ does not.
                if displayed.startswith("US$"):
                    record["currency"] = "USD"
                amount = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
                record["price"] = amount
    return record
