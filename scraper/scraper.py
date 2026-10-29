"""Retrieve public laptop pages and extract fields without database access."""

import json
import re
import random
import time
import threading
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit
from curl_cffi import requests
from bs4 import BeautifulSoup


PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    "walmart": r"/ip/(?:[^/]+/)?(\d+)(?:/|$)",
}

class BlockError(ValueError):
    """Retailer is refusing automated access, no more requests to it this run."""
    pass

MIN_SECONDS_BETWEEN_REQUESTS = 3.0
BLOCKED_RETAILERS = set()
_last_request = {}
_lock = threading.Lock()

def identify_product(url):
    """Accept only HTTPS product URLs at our four US retailers."""
    try:
        parts = urlsplit(url)
        invalid = parts.scheme != "https" or parts.username or parts.password or parts.port is not None
    except ValueError:
        raise ValueError("Malformed product URL.") from None
    if invalid:
        raise ValueError("Use an HTTPS product URL without login details or a port.")
    for retailer, pattern in PRODUCT_PATHS.items():
        if parts.hostname in {f"{retailer}.com", f"www.{retailer}.com"}:
            match = re.search(pattern, parts.path)
            if match:
                product_id = next(value for value in match.groups() if value)
                if retailer == "target":
                    # Verified against the real 95288385?preselect=91122087 page:
                    # the path is the family; preselect identifies the child TCIN.
                    # Keep the original query intact in product_url.
                    selected = parse_qs(parts.query, keep_blank_values=True).get("preselect")
                    if selected is not None:
                        if len(selected) != 1 or not re.fullmatch(r"\d+", selected[0]):
                            raise ValueError("Target preselect must identify exactly one numeric product variant.")
                        product_id = selected[0]
                return retailer, product_id
    raise ValueError("Use an Amazon, Best Buy, Target, or Walmart US product page.")


def clean_url(url):
    url = url.strip()
    identify_product(url)
    # Generic normalization only: lowercase host and drop the browser fragment.
    # Preserve the ENTIRE query, including order, encoding, blanks and repeats.
    parts = urlsplit(url)
    query = f"?{parts.query}" if parts.query else ""
    return f"https://{parts.hostname}{parts.path}{query}"


def unique_urls(urls):
    """Deduplicate normalized URLs, preserving input order and distinct variants."""
    unique = []
    seen = set()
    for url in urls:
        try:
            normalized = clean_url(url)
        except ValueError:
            normalized = url.strip()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


def target_family_id(url):
    """TCIN in a Target path, ignoring ?preselect= (which names the child)."""
    match = re.search(PRODUCT_PATHS["target"], urlsplit(url).path)
    return match.group(1) if match else None


def canonical_matches(found, expected, requested_url):
    """A safety check that confirms you are on the right product page before wasting time pulling data from it."""
    if found == expected:
        return True
    return (expected[0] == "target" and found[0] == "target" and found[1] == target_family_id(requested_url))


def same_requested_product(original, destination):
    """Unknown query parameters may select variants: redirects must preserve them."""
    return (identify_product(original) == identify_product(destination)
            and urlsplit(original).query == urlsplit(destination).query)


def wait_for_turn(retailer):
    """Refuse a retailer that blocked earlier, otherwise pause."""
    with _lock:
        if retailer in BLOCKED_RETAILERS:
            raise BlockError(f"{retailer} blocked automated access earlier in this run; not requesting it again.")
        now = time.monotonic()
        last = _last_request.get(retailer)
        start = now if last is None else max(now, last + MIN_SECONDS_BETWEEN_REQUESTS + random.uniform(0, 1))
        _last_request[retailer] = start 
    
    pause = start - time.monotonic()
    if pause > 0:
        time.sleep(pause)
    with _lock:
        if retailer in BLOCKED_RETAILERS:
            raise BlockError(f"{retailer} blocked automated access while this request was waiting.")


def _guarded(fetch, url):
    retailer, _ = identify_product(clean_url(url))
    wait_for_turn(retailer)
    try:
        return fetch(url)
    except BlockError:
        with _lock:
            BLOCKED_RETAILERS.add(retailer)
            raise


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup.select("script, style"):
        tag.decompose()
    lower = soup.get_text(" ", strip=True).lower()
    markers = ["robot check", "validatecaptcha", "verify you are human",
               "verify you're human", "press & hold", "access denied"]
    if any(marker in lower for marker in markers) or soup.select_one('input[name="captchacharacters"]'):
        raise BlockError("Retailer returned a bot check or access-denied page. Stop here.")


def _fetch_page(url):
    url = clean_url(url)
    try:
        for attempt in range(4):
            response = requests.get(
                url, timeout=25, allow_redirects=False,
                headers={"User-Agent": "ShoppieClassroom/1.0 (educational product-page reader)"},
            )
            if response.status_code not in (301, 302, 303, 307, 308):
                break
            destination = urljoin(url, response.headers.get("Location", ""))
            try:
                same_product = same_requested_product(url, destination)
            except ValueError:
                same_product = False
            if not same_product:
                raise ValueError("Redirect left the requested product. Review its exact URL in your browser.")
            url = clean_url(destination)
        else:
            raise ValueError("Too many product-page redirects; no record collected.")
    except requests.RequestException:
        raise ValueError("Page request failed or timed out; no record collected.") from None
    if response.status_code in (403, 429):
        raise BlockError(f"Retailer returned HTTP {response.status_code} (blocked or rate limit). Stop here.")
    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
    check_page(response.text)
    return response.text


def _fetch_rendered_page(url):
    """Fetch protected e-commerce pages by impersonating a real browser's TLS fingerprint."""
    try:
        from curl_cffi import requests as curl_requests
    except ImportError:
        raise ValueError("Install curl_cffi to use advanced scraping.") from None
    
    url = clean_url(url)
    headers = {
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Accept-Encoding": "gzip, deflate, br",
        "Connection": "keep-alive",
        "Upgrade-Insecure-Requests": "1",
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36"
    }
    
    try:
        response = curl_requests.get(url, headers=headers, impersonate="chrome", timeout=30)
        if response.status_code != 200:
            raise ValueError(f"Target returned status code: {response.status_code}")
        html = response.text
        check_page(html)
    except Exception as e:
        raise ValueError(f"Failed to fetch page securely: {e}") from None
        
    return html


def fetch_page(url):
    return _guarded(_fetch_page, url)


def fetch_rendered_page(url):
    return _guarded(_fetch_rendered_page, url)


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
                if identify_product(urljoin(url, reference)) == identity:
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
    tag = soup.select_one(f'meta[property="product:{field}"]')
    return tag.get("content") if tag else None


def target_embedded_product_info(soup, product_id):
    """Read Target layout modules explicitly bound to this TCIN for title, price, and availability."""
    script = soup.select_one('script#__NEXT_DATA__[type="application/json"]')
    if script is None:
        return None, None, None
    try:
        queries = json.loads(script.get_text())["props"]["dehydratedState"]["queries"]
        titles = set()
        prices = set()
        availability = None
        
        for query in queries:
            payload = query.get("state", {}).get("data") or {}
            layout = (payload.get("data") or {}).get("layout") or {}
            for zone in layout.get("zones", []):
                for group in zone.get("module_groups", []):
                    for module in group.get("modules", []):
                        for item in module.get("module_data", {}).get("data_by_tcin", []):
                            if str(item.get("tcin")) == str(product_id):
                                title = item.get("title")
                                if isinstance(title, str) and title.strip():
                                    titles.add(title.strip())
                                
                                price_data = item.get("price", {})
                                current_price = price_data.get("current_retail") or price_data.get("price")
                                if current_price is not None:
                                    prices.add(str(current_price))
                                    
                                fulfillment = item.get("fulfillment", {})
                                if fulfillment:
                                    availability = True
                                    
    except (ValueError, KeyError, TypeError, AttributeError):
        return None, None, None
        
    if len(titles) > 1:
        raise ValueError("Target embedded data contains conflicting titles for the selected variant.")
        
    return next(iter(titles), None), next(iter(prices), None), availability


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get("href"):
        found = identify_product(urljoin(url, canonical["href"]))
        if not canonical_matches(found, (retailer, product_id), url):
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
        record["title"] = product.get("name")
        offers = product.get("offers")
        if isinstance(offers, list) and len(offers) > 0:
            offers = offers[0]
        if offers:
            if not isinstance(offers, dict):
                raise ValueError("Expected an Offer dictionary.")
            record["extraction_method"] = "json-ld"
            
            price = offers.get("price") or offers.get("lowPrice")
            if price is not None:
                record["price"] = str(price)
                
            record["currency"] = offers.get("priceCurrency", "USD")
            
            availability = offers.get("availability")
            if availability:
                if isinstance(availability, str):
                    record["availability"] = "InStock" in availability
                else:
                    record["availability"] = bool(availability)
                    
            seller = offers.get("seller")
            record["seller"] = seller.get("name") if isinstance(seller, dict) else "Target"
            return record

    titles = {
        "amazon": "#productTitle", "bestbuy": "h1",
        "target": 'h1[data-test="product-title"], h1',
        "walmart": 'h1[itemprop="name"], h1',
    }
    record["title"] = text(soup, titles[retailer]) or record["title"]
    
    if retailer == "target":
        embedded_title, embedded_price, embedded_availability = target_embedded_product_info(soup, product_id)
        if embedded_title:
            record["title"] = embedded_title
        if embedded_price:
            record["price"] = embedded_price
            record["currency"] = "USD"
            record["extraction_method"] = "embedded-next-data"
        if embedded_availability is not None:
            record["availability"] = embedded_availability

    record["price"] = record["price"] or meta(soup, "price:amount") or meta(soup, "price")
    record["currency"] = record["currency"] or meta(soup, "price:currency") or meta(soup, "priceCurrency")
    record["availability"] = record["availability"] if record["availability"] is not None else meta(soup, "availability")
    
    price_selectors = {
        "bestbuy": '[data-testid="customer-price"]',
        "target": '[data-test="product-price"]',
    }
    if retailer in price_selectors and record["price"] is None:
        displayed = text(soup, price_selectors[retailer])
        if displayed and re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
            record["price"] = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            if displayed.startswith("US$"):
                record["currency"] = "USD"
                
    if retailer == "amazon":
        container = soup.select_one("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div")
        if container and record["price"] is None:
            displayed = text(container, ".a-price:not(.a-text-price) .a-offscreen")
            if displayed:
                if displayed.startswith("US$"):
                    record["currency"] = "USD"
                amount = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
                record["price"] = amount
                
    return record