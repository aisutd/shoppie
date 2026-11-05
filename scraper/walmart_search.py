"""Discover Walmart product pages from its public search results."""

import html
import re
from datetime import datetime, timezone
from urllib.parse import urlencode, urljoin, urlsplit

from bs4 import BeautifulSoup
from curl_cffi import requests as cffi_requests
from curl_cffi.requests.exceptions import RequestException

from scraper.tech_scraper import check_page, clean_url, identify_product


SEARCH_ROOT = "https://www.walmart.com/search"
WALMART_ROOT = "https://www.walmart.com"
MAX_PRODUCTS = 8
_PRODUCT_PATH = re.compile(
    r"""(?<![A-Za-z0-9])(/ip/(?:[^/"'\\\s<>]+/)?\d+)(?:[/?#"'\\\s<>]|$)"""
)
_PRICE = re.compile(
    r"\bPrice(?:\s+Now)?\s*\$\s*([0-9][0-9,]*(?:\.\d{2})?)",
    re.I,
)
_WAS_PRICE = re.compile(
    r"\bWas\s*\$\s*([0-9][0-9,]*(?:\.\d{2})?)",
    re.I,
)


class WalmartDiscoveryError(ValueError):
    """A safe, user-facing Walmart discovery failure."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def search_url(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError("Enter a product search under 300 characters.")

    return SEARCH_ROOT + "?" + urlencode({"q": " ".join(query.split())})


def _checked_soup(markup):
    try:
        check_page(markup)
    except ValueError as error:
        raise WalmartDiscoveryError("page_rejected", str(error)) from None
    return BeautifulSoup(markup, "html.parser")


def parse_search_results(markup, limit=MAX_PRODUCTS):
    """Return unique, validated Walmart product links from rendered page data."""
    limit = max(1, min(limit, MAX_PRODUCTS))
    soup = _checked_soup(markup)
    candidates = [link.get("href") for link in soup.select("a[href]")]

    # Walmart sometimes includes product URLs in serialized page data instead
    # of rendered anchors. Accept only paths that pass the product URL validator.
    searchable_markup = html.unescape(markup)
    searchable_markup = searchable_markup.replace(r"\/", "/")
    searchable_markup = searchable_markup.replace(r"\u002F", "/")
    searchable_markup = searchable_markup.replace(r"\u002f", "/")
    candidates.extend(match.group(1) for match in _PRODUCT_PATH.finditer(searchable_markup))

    products = []
    seen = set()
    for candidate in candidates:
        if not isinstance(candidate, str):
            continue
        try:
            product_url = clean_url(urljoin(WALMART_ROOT, candidate))
            retailer, product_id = identify_product(product_url)
        except ValueError:
            continue

        identity = (retailer, product_id)
        if retailer != "walmart" or identity in seen:
            continue

        seen.add(identity)
        products.append(product_url)
        if len(products) >= limit:
            return products

    visible_text = soup.get_text(" ", strip=True)
    if re.search(
        r"\b(no results|no products found|0 results|we couldn.t find)\b",
        visible_text,
        re.I,
    ):
        return []

    if products:
        return products
    raise WalmartDiscoveryError(
        "page_rejected",
        "Walmart returned no recognizable product links; its search markup may have changed.",
    )


def parse_search_products(markup, limit=MAX_PRODUCTS):
    """Extract current price and item details explicitly shown in result cards."""
    limit = max(1, min(limit, MAX_PRODUCTS))
    soup = _checked_soup(markup)
    products = []
    seen = set()

    for card in soup.select("[data-item-id]"):
        product_url = None
        product_id = None
        for link in card.select('a[href*="/ip/"]'):
            try:
                candidate_url = clean_url(
                    urljoin(WALMART_ROOT, link["href"])
                )
                retailer, candidate_id = identify_product(candidate_url)
            except (KeyError, ValueError):
                continue
            if retailer == "walmart":
                product_url = candidate_url
                product_id = candidate_id
                break

        if product_url is None or product_id in seen:
            continue

        title_node = card.select_one(
            '[data-automation-id="product-title"], '
            '[data-test-id="gpt-global-product-title"]'
        )
        price_node = card.select_one(
            '[data-testid="unified-global-product-price-a11y-text"]'
        )
        if title_node is None or price_node is None:
            continue

        title = title_node.get_text(" ", strip=True)
        price_text = price_node.get_text(" ", strip=True)
        price_match = _PRICE.search(price_text)
        if len(title) < 5 or price_match is None:
            continue
        price = price_match.group(1).replace(",", "")
        regular_price_match = _WAS_PRICE.search(price_text)
        regular_price = (
            regular_price_match.group(1).replace(",", "")
            if regular_price_match
            else None
        )
        if regular_price is not None and float(regular_price) <= float(price):
            regular_price = None

        image_url = None
        for image in card.select("img[src]"):
            candidate_image = urljoin(WALMART_ROOT, image["src"])
            image_parts = urlsplit(candidate_image)
            if (
                image_parts.scheme == "https"
                and image_parts.hostname
                and image.get("alt")
            ):
                image_url = candidate_image
                break

        products.append(
            {
                "title": title,
                "description": None,
                "image_url": image_url,
                "price": price,
                "regular_price": regular_price,
                "currency": "USD",
                "product_url": product_url,
                "source": "walmart.com",
                "category": "other",
                "scraped_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        seen.add(product_id)
        if len(products) >= limit:
            break

    return products


def _search_request(url, timeout):
    try:
        with cffi_requests.Session() as session:
            return session.get(
                url,
                timeout=timeout,
                allow_redirects=False,
                impersonate="chrome",
            )
    except RequestException:
        raise WalmartDiscoveryError(
            "network_error",
            "Walmart search could not be reached or timed out.",
        ) from None


def _search_markup(query, timeout):
    response = _search_request(search_url(query), timeout)

    if response.status_code != 200:
        raise WalmartDiscoveryError(
            "http_error",
            f"Walmart search returned HTTP {response.status_code}.",
        )
    if "text/html" not in response.headers.get("Content-Type", "").lower():
        raise WalmartDiscoveryError(
            "unexpected_response",
            "Walmart search did not return an HTML page.",
        )
    return response.text


def discover_walmart_urls(query, limit=MAX_PRODUCTS, timeout=8):
    markup = _search_markup(query, timeout)
    return parse_search_results(markup, limit)


def discover_walmart_products(query, limit=MAX_PRODUCTS, timeout=8):
    """Fetch Walmart search results and extract product card records."""
    markup = _search_markup(query, timeout)
    return parse_search_products(markup, limit)
