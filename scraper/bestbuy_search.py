"""Discover a small set of Best Buy product pages from shopping keywords.

This is separate from tech_scraper: a search page contains many products,
whereas extract_product() expects one product page. No database access here.
"""

import json
import logging
import re
from datetime import datetime, timezone
from concurrent.futures import ThreadPoolExecutor
from urllib.parse import urlencode, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from scraper.tech_scraper import check_page, clean_url, identify_product


SEARCH_ROOT = "https://www.bestbuy.com/site/searchpage.jsp"
MAX_PRODUCTS = 16
logger = logging.getLogger(__name__)


def _search_soup(html):
    """Resolve explicit React streamed fragments without executing JavaScript."""
    check_page(html)
    soup = BeautifulSoup(html, "html.parser")
    used = set()
    for boundary, segment_id in re.findall(r'\$RC\("(B:[\w]+)","(S:[\w]+)"\)', html):
        placeholder = soup.find("template", id=boundary)
        segment = soup.find(id=segment_id)
        if placeholder is not None and segment is not None and segment_id not in used:
            if placeholder in segment.descendants:
                continue
            used.add(segment_id)
            placeholder.replace_with(*list(segment.contents))
    return soup


def parse_search_cards(html):
    """Read only a card's own title link and explicit current customer price.

    Never pair a page-wide first price with an unrelated product. Missing,
    multiple, financing, regular or ambiguous prices are not valid fallbacks.
    """
    soup = _search_soup(html)
    records = {}
    for card in soup.select('.product-list-item-sv, .sku-item, [data-testid="product-card"]'):
        titles = card.select('a.product-list-item-link, .sku-title a')
        if len(titles) != 1:
            continue
        try:
            url = clean_url(urljoin(SEARCH_ROOT, titles[0]["href"]))
            if identify_product(url)[0] != "bestbuy":
                continue
        except (ValueError, KeyError):
            continue
        amounts = card.select('[data-testid="price-block-customer-price"] .sr-only')
        if len(amounts) != 1:
            continue
        amount = amounts[0].get_text(" ", strip=True)
        if not re.fullmatch(r"\$(?:\d{1,3}(?:,\d{3})+|\d+)\.\d{2}", amount):
            continue
        image = card.select_one('img[data-testid="product-image"], .product-image img')
        records[url] = {
            "title": titles[0].get_text(" ", strip=True), "description": None,
            "image_url": urljoin(SEARCH_ROOT, image["src"]) if image and image.get("src") else None,
            "price": amount[1:].replace(",", ""), "currency": "USD",
            "product_url": url, "source": "bestbuy.com", "category": "electronics",
            "scraped_at": datetime.now(timezone.utc).isoformat(),
        }
    return records


def recover_search_card(url, timeout=8):
    """On transport failure, search the retailer's public model-name endpoint.

    A fallback is accepted only if its product ID AND variant query agree with
    the requested URL. It still goes through the collector's normal validation.
    No challenge/HTTP rejection is retried here, and no model generates prices.
    """
    identify_product(url)
    # A numeric SKU query redirects back to the broken detail-page endpoint.
    # The observed URL's slug supplies keywords, never an invented URL/price.
    path = urlsplit(url).path
    match = re.search(r"/(?:product|site)/([^/]+)/", path)
    if not match:
        raise ValueError("No model-name keywords are available for this listing.")
    keywords = match.group(1).replace("-", " ")[:280]
    try:
        response = _search_request(search_url(keywords), timeout)
    except Exception:
        raise ValueError("Public model search could not be reached for exact-product recovery.") from None
    if response.status_code != 200 or "text/html" not in response.headers.get("Content-Type", "").lower():
        raise ValueError("Public model search was unavailable for exact-product recovery.")
    matches = [record for candidate, record in parse_search_cards(response.text).items()
               if identify_product(candidate) == identify_product(url)
               and urlsplit(candidate).query == urlsplit(url).query]
    if len(matches) != 1:
        raise ValueError("Public model search did not verify this exact listing and price.")
    return matches[0]


class DiscoveryError(ValueError):
    """A specific, safe explanation that can be shown in the result page."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def search_url(query):
    if not isinstance(query, str) or not query.strip() or len(query) > 300:
        raise ValueError("Enter a product search under 300 characters.")
    # urlencode prevents query text from changing the host/path or parameters.
    return SEARCH_ROOT + "?" + urlencode({"st": " ".join(query.split())})


def _list_urls(value):
    """Read explicit ItemList entries, not arbitrary prices in script text."""
    if isinstance(value, list):
        for node in value:
            yield from _list_urls(node)
    elif isinstance(value, dict):
        kind = value.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "ItemList" in kinds:
            for entry in value.get("itemListElement", []):
                if not isinstance(entry, dict):
                    continue
                item = entry.get("item", entry)
                if isinstance(item, str):
                    yield item
                elif isinstance(item, dict) and isinstance(item.get("url"), str):
                    yield item["url"]
        yield from _list_urls(value.get("@graph"))


def parse_search_results(html, limit=MAX_PRODUCTS):
    """Extract allowed product links and deduplicate path aliases by product ID."""
    soup = _search_soup(html)
    links = []
    # Prefer product-card links to unrelated navigation and recommendations.
    cards = soup.select(
        '.sku-item, [data-testid="product-card"], '
        '[data-testid="product-list-item"], .product-list-item'
    )
    for card in cards:
        links.extend(a.get("href") for a in card.select("a[href]"))
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            links.extend(_list_urls(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    # Layout fallback: URLs still have to identify actual Best Buy products.
    if not links:
        links = [a.get("href") for a in soup.select("a[href]")]

    products, seen = [], set()
    for href in links:
        if not isinstance(href, str):
            continue
        try:
            url = clean_url(urljoin(SEARCH_ROOT, href))
            retailer, product_id = identify_product(url)
        except ValueError:
            continue
        # Retain query strings: unknown parameters may select product variants.
        identity = (product_id, urlsplit(url).query)
        if retailer != "bestbuy" or identity in seen:
            continue
        seen.add(identity)
        products.append(url)
        if len(products) >= max(1, min(limit, MAX_PRODUCTS)):
            break
    if products:
        return products
    visible = soup.get_text(" ", strip=True)
    if re.search(r"\b(no results|no products found|0 results|we couldn.t find)\b", visible, re.I):
        return []
    raise ValueError("Best Buy returned no recognizable product links; its layout may have changed.")


def _search_request(url, timeout):
    """Require the collector transport; never silently change HTTP behavior."""
    try:
        from curl_cffi import requests as cffi_requests
    except ImportError:
        raise DiscoveryError(
            "missing_dependency",
            "The backend Python environment is missing curl_cffi. Run python3 -m pip install curl_cffi==0.13.0 and restart the backend.",
        ) from None
    with cffi_requests.Session() as session:
        return session.get(url, timeout=timeout, allow_redirects=False, impersonate="safari_ios")


def _discover_page(url, limit, timeout):
    """Read one public search page; never follow a verification/redirect page."""
    try:
        response = _search_request(url, timeout)
        if response.status_code != 200:
            raise DiscoveryError("http_error", f"Best Buy search returned HTTP {response.status_code}.")
        if "text/html" not in response.headers.get("Content-Type", "").lower():
            raise DiscoveryError("unexpected_response", "Best Buy search did not return an HTML page.")
        try:
            return parse_search_results(response.text, limit)
        except ValueError as error:
            # Parser-generated messages contain no credentials or page payloads.
            raise DiscoveryError("page_rejected", str(error)) from None
    except (requests.RequestException, OSError):
        raise DiscoveryError("network_error", "Best Buy search could not be reached or timed out.") from None


def discovery_pages(query):
    """Bounded recall expansion, not permission to relax the user's filters.

    Some current search pages server-render just their first listing. Pagination
    and alternate wording can expose other listings. Unspecified MacBook screen
    sizes are explored explicitly; a specified size is never expanded.
    """
    base = search_url(query)
    pages = [base, base + "&cp=2", base + "&cp=3"]
    if re.search(r"\bmacbook\b", query, re.I) and not re.search(
        r'\b(?:13|14|15|16)(?:\.\d+)?\s*(?:-?\s*inch|[\"″])|\bscreen\b', query, re.I
    ):
        pages.extend(search_url(query + suffix) for suffix in (" 13 inch", " 15 inch"))
    else:
        alternate = re.sub(r"\b(\d+)\s*GB\b", r"\1 GB", query, flags=re.I)
        if alternate != query:
            pages.append(search_url(alternate))
    return list(dict.fromkeys(pages))


def discover_bestbuy_urls(query, limit=MAX_PRODUCTS, timeout=8):
    """Combine up to five result pages, retaining distinct real product URLs.

    The primary page must succeed. Secondary failures do not discard successful
    candidates. At most three secondary requests run concurrently, each bounded
    by its own timeout; product extraction still validates every candidate.
    """
    limit = max(1, min(limit, MAX_PRODUCTS))
    pages = discovery_pages(query)
    products = _discover_page(pages[0], limit, timeout)
    if len(products) >= limit or not products:
        return products

    def extra_page(url):
        try:
            return _discover_page(url, limit, timeout)
        except Exception:
            logger.warning("An additional Best Buy discovery page was unavailable")
            return []

    seen = {(identify_product(url)[1], urlsplit(url).query) for url in products}
    with ThreadPoolExecutor(max_workers=3) as pool:
        # map preserves plan order, so selection does not depend on network timing.
        for found in pool.map(extra_page, pages[1:]):
            for url in found:
                identity = (identify_product(url)[1], urlsplit(url).query)
                if identity not in seen and len(products) < limit:
                    seen.add(identity)
                    products.append(url)
    return products
