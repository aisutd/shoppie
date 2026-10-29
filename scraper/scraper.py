"""Retrieve public laptop pages and extract fields without database access."""

import json
import os
from pathlib import Path
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
import threading
import time
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
    if not isinstance(url, str) or any(character.isspace() for character in url):
        raise ValueError("Malformed product URL: embedded whitespace is not allowed")
    try:
        parts = urlsplit(url)
        invalid = parts.scheme != "https" or parts.username or parts.password or parts.port
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
    # No retailer-specific parameter removal has been verified for this lesson.
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
            # Keep invalid inputs for the pipeline to report once, without logging them.
            normalized = url.strip()
        if normalized not in seen:
            seen.add(normalized)
            unique.append(normalized)
    return unique


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
        start = now if last is None else max(now, last + MIN_SECONDS_BETWEEN_REQUESTS)
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
    # Inspect visible text, not scripts that may merely mention a bot-check route.
    for tag in soup.select("script, style"):
        tag.decompose()
    lower = soup.get_text(" ", strip=True).lower()
    markers = ["robot check", "validatecaptcha", "verify you are human",
               "verify you're human", "press & hold", "access denied", "too many requests",
               "sign in to continue", "unusual traffic"]
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
    # Only redirects within the same retailer AND product identity are followed.
    if response.status_code in {401, 403, 429, 451}:
        raise BlockError(f"Retailer returned HTTP {response.status_code}; stop here.")
    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
    check_page(response.text)
    return response.text


def read_browser_page(page, url):
    """Wait for explicit product fields in a normal Chromium page."""
    response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
    if response is None:
        raise ValueError("Browser did not receive a successful product page")
    if response.status != 200:
        raise ValueError(f"Retailer returned HTTP {response.status}; browser collection stopped")
    for attempt in range(10):
        try:
            same_product = same_requested_product(url, page.url)
        except ValueError:
            same_product = False
        if not same_product:
            raise ValueError("Browser redirected away from the requested product")
        html = page.content()
        check_page(html)
        candidate = extract_product(html, url)
        if candidate["title"] and candidate["price"] is not None and candidate["currency"]:
            return html
        page.wait_for_timeout(1000)
    # checks identity and access once more after the last rendering wait
    if not same_requested_product(url, page.url):
        raise ValueError("Browser redirected away from the requested product")
    html = page.content()
    check_page(html)
    return html


def _fetch_rendered_page(url, headless=True):
    """Render with installed Chromium; never solve a retailer challenge."""
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise ValueError("Install Playwright and its Chromium browser to use --browser") from None
    url = clean_url(url)
    os.environ.setdefault("PLAYWRIGHT_BROWSERS_PATH", str(Path(__file__).resolve().parents[1] / ".local/browsers"))
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(headless=headless) as browser:
                page = browser.new_page()
                # aborts changed-product navigations before another page is requested
                def guard(route):
                    request = route.request
                    if request.is_navigation_request() and request.frame == page.main_frame:
                        try:
                            allowed = same_requested_product(url, request.url)
                        except ValueError:
                            allowed = False
                        if not allowed:
                            route.abort()
                            return
                    route.continue_()
                page.route("**/*", guard)
                return read_browser_page(page, url)
    except Error:
        raise ValueError("Browser load failed; check installed Chromium and network access") from None


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
    # Page-level product metadata describes this page. Unscoped itemprop tags
    # can belong to a recommendation; never mix them into the main title.
    tag = soup.select_one(f'meta[property="product:{field}"]')
    return tag.get("content") if tag else None


def named_value(value):
    """Read a visible JSON-LD name or plain string without guessing."""
    if isinstance(value, str):
        return value.strip() or None
    if isinstance(value, dict) and isinstance(value.get("name"), str):
        return value["name"].strip() or None
    return None


def product_details(product):
    """Keep only details explicitly attached to the selected Product node."""
    details = {
        "brand": named_value(product.get("brand")),
        "model": named_value(product.get("model")),
        "category": named_value(product.get("category")),
        "description": named_value(product.get("description")),
        "gtin": None, "attributes": {},
    }
    if details["description"]:
        details["description"] = BeautifulSoup(details["description"], "html.parser").get_text(" ", strip=True) or None
    for key in ("gtin14", "gtin13", "gtin12", "gtin8", "gtin"):
        if isinstance(product.get(key), str) and product[key].strip():
            details["gtin"] = product[key].strip()
            break
    properties = product.get("additionalProperty") or []
    if isinstance(properties, dict):
        properties = [properties]
    if isinstance(properties, list):
        names = {"cpu": "cpu", "processor": "cpu", "color": "color", "ram": "ram_gb", "memory": "ram_gb",
                 "ram size": "ram_gb", "system memory (ram)": "ram_gb",
                 "system memory ram": "ram_gb", "storage": "storage_gb",
                 "total storage capacity": "storage_gb", "processor model": "cpu",
                 "screen size": "screen_inches"}
        for item in properties:
            if not isinstance(item, dict):
                continue
            field = names.get(str(item.get("name", "")).strip().lower())
            value = item.get("value")
            parsed = None
            if field in {"color", "cpu"} and isinstance(value, str):
                parsed = value.strip() or None
            elif field and isinstance(value, (str, int, float)) and not isinstance(value, bool):
                unit = item.get("unitText") or item.get("unitCode") or ""
                displayed = f"{value} {unit}".strip()
                units = "GB|TB" if field in {"ram_gb", "storage_gb"} else "in|inch|inches"
                match = re.fullmatch(rf"\s*(\d+(?:\.\d+)?)\s*({units})\s*", displayed, re.I)
                if match:
                    number = float(match.group(1)) * (1000 if match.group(2).upper() == "TB" else 1)
                    parsed = int(number) if number.is_integer() else number
            if field and parsed is not None:
                details["attributes"] = merge_specs(details["attributes"], {field: parsed})
    if isinstance(product.get("color"), str):
        details["attributes"] = merge_specs(details["attributes"], {"color": product["color"].strip() or None})
    return details


def target_embedded_product_info(soup, product_id):
    """Read only explicit selected-TCIN fields; fulfillment alone proves no stock."""
    script = soup.select_one('script#__NEXT_DATA__[type="application/json"]')
    values = {key: set() for key in ('title', 'price', 'currency', 'availability')}
    if script is None:
        return dict.fromkeys(values)
    try:
        queries = json.loads(script.get_text())['props']['dehydratedState']['queries']
        for query in queries:
            layout = ((query.get('state', {}).get('data') or {}).get('data') or {}).get('layout') or {}
            for zone in layout.get('zones', []):
                for group in zone.get('module_groups', []):
                    for module in group.get('modules', []):
                        for item in module.get('module_data', {}).get('data_by_tcin', []):
                            if str(item.get('tcin')) != str(product_id):
                                continue
                            price = item.get('price') or {}
                            price = price if isinstance(price, dict) else {}
                            fields = {'title': item.get('title'), 'price': price.get('current_retail', price.get('price')),
                                      'currency': price.get('currency') or price.get('priceCurrency'),
                                      'availability': item.get('availability')}
                            for key, value in fields.items():
                                if isinstance(value, (str, int, float)) and not isinstance(value, bool):
                                    values[key].add(str(value).strip())
    except (ValueError, KeyError, TypeError, AttributeError):
        return dict.fromkeys(values)
    if any(len(items) > 1 for items in values.values()):
        raise ValueError('Target embedded data contains conflicting titles or selected-variant fields.')
    return {key: next(iter(items), None) for key, items in values.items()}


def target_embedded_title(soup, product_id):
    return target_embedded_product_info(soup, product_id)['title']


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    # Refuse a different selected product (for example an Amazon variant change).
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get("href"):
        try:
            same_identity = identify_product(urljoin(url, canonical["href"])) == (retailer, product_id)
        except ValueError:
            same_identity = False
        if not same_identity:
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
        "brand": None, "model": None, "category": None, "gtin": None,
        "description": None, "shipping_cost": None,
        "attributes": {},
    }
    product = main_product(soup, url)
    if product:
        record["extraction_method"] = "json-ld"
        record["title"] = product.get("name")
        if not isinstance(record["title"], str) or not record["title"].strip():
            headings = {"amazon": "#productTitle", "bestbuy": "h1",
                        "target": 'h1[data-test="product-title"], h1',
                        "walmart": 'h1[itemprop="name"], h1'}
            record["title"] = text(soup, headings[retailer])
        record.update(product_details(product))
        # compares only explicit page-level identity fields, not recommendations
        for field in ("brand", "model"):
            declared = meta(soup, field)
            if declared and record[field] and " ".join(declared.casefold().split()) != " ".join(record[field].casefold().split()):
                raise ValueError(f"Conflicting main-product {field}; selected listing is inconsistent")
            record[field] = record[field] or declared
        offers = product.get("offers")
        if isinstance(offers, list) and len(offers) == 1:
            offers = offers[0]
        # A range/aggregate or multiple sellers is not one exact price.
        if not isinstance(offers, dict) or not schema_type(offers, "Offer"):
            raise ValueError("Expected one exact Offer; price ranges/multiple offers are rejected.")
        if offers.get("url"):
            if not isinstance(offers["url"], str) or identify_product(urljoin(url, offers["url"])) != (retailer, product_id):
                raise ValueError("Offer belongs to a different product; no price collected.")
        record["price"] = offers.get("price")
        record["currency"] = offers.get("priceCurrency")
        record["availability"] = offers.get("availability")
        visible_availability = meta(soup, "availability")
        known = {"InStock", "OutOfStock", "SoldOut", "Discontinued", "PreOrder", "BackOrder"}
        normalize_stock = lambda value: re.sub(r"^https?://schema\.org/", "", value) if isinstance(value, str) else None
        left, right = normalize_stock(record["availability"]), normalize_stock(visible_availability)
        if left in known and right in known and left != right:
            raise ValueError("Conflicting main-product availability; review the offer manually")
        if record["availability"] is None:
            record["availability"] = visible_availability
        condition = offers.get("itemCondition") or product.get("itemCondition")
        conditions = {"NewCondition": "new", "UsedCondition": "used", "RefurbishedCondition": "refurbished"}
        if isinstance(condition, str) and condition.rsplit("/", 1)[-1] in conditions:
            record["attributes"]["condition"] = conditions[condition.rsplit("/", 1)[-1]]
        shipping = offers.get("shippingDetails")
        if isinstance(shipping, dict):
            rate = shipping.get("shippingRate")
            if isinstance(rate, dict) and rate.get("currency") == record["currency"]:
                record["shipping_cost"] = rate.get("value")
        seller = offers.get("seller")
        record["seller"] = seller.get("name") if isinstance(seller, dict) else None
        # rejects stale structured prices when a scoped main price contradicts them
        selectors = {"bestbuy": '[data-testid="customer-price"]', "target": '[data-test="product-price"]',
                     "amazon": '#corePriceDisplay_desktop_feature_div .a-price:not(.a-text-price) .a-offscreen'}
        displayed = meta(soup, "price:amount") or (text(soup, selectors[retailer]) if retailer in selectors else None)
        if displayed and re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
            amount = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            try:
                if record["price"] is not None and Decimal(str(record["price"])) != Decimal(amount):
                    raise ValueError("Conflicting main-product prices; review the page manually")
            except InvalidOperation:
                pass
        record["attributes"] = merge_specs(record["attributes"], extract_specs(record["title"] or ""))
        return record

    # These fallbacks only inspect the main product's named HTML elements.
    # No whole-page price regex: it could pick a monthly payment or accessory.
    titles = {
        "amazon": "#productTitle", "bestbuy": "h1",
        "target": 'h1[data-test="product-title"], h1',
        "walmart": 'h1[itemprop="name"], h1',
    }
    record["title"] = text(soup, titles[retailer])
    record["brand"] = meta(soup, "brand")
    record["model"] = meta(soup, "model")
    record["category"] = meta(soup, "category")
    record["gtin"] = meta(soup, "gtin")
    record["description"] = meta(soup, "description")
    if retailer == "target":
        # Rendering sometimes removes the main heading while this TCIN-bound
        # title remains in public page data. Price/currency must still be explicit.
        embedded_title = target_embedded_title(soup, product_id)
        if embedded_title:
            record["title"] = embedded_title
    record["price"] = meta(soup, "price:amount") or meta(soup, "price")
    record["currency"] = meta(soup, "price:currency") or meta(soup, "priceCurrency")
    record["availability"] = meta(soup, "availability")
    price_selectors = {
        "bestbuy": '[data-testid="customer-price"]',
        "target": '[data-test="product-price"]',
    }
    if retailer in price_selectors and record["price"] is None:
        displayed = text(soup, price_selectors[retailer])
        # Match only a single whole price in the named main-product price element.
        if displayed and re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
            record["price"] = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            if displayed.startswith("US$"):
                record["currency"] = "USD"
    if retailer == "amazon":
        container = soup.select_one("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div")
        if container and record["currency"] is None:
            code = container.select_one('[itemprop="priceCurrency"], [data-a-currency-code]')
            if code:
                record["currency"] = code.get("content") or code.get("data-a-currency-code")
        if container and record["price"] is None:
            displayed = text(container, ".a-price:not(.a-text-price) .a-offscreen")
            if displayed:
                # US$ explicitly identifies currency; a bare $ does not.
                if displayed.startswith("US$"):
                    record["currency"] = "USD"
                amount = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
                record["price"] = amount
    if retailer == "target":
        # never substitutes a family price, currency guess, or fulfillment boolean
        embedded = target_embedded_product_info(soup, product_id)
        for key in ('price', 'currency', 'availability'):
            if record[key] is not None and embedded[key] is not None and str(record[key]) != embedded[key]:
                raise ValueError('Target selected-variant metadata is conflicting')
            if record[key] is None:
                record[key] = embedded[key]
    record["attributes"] = extract_specs(record["title"] or "")
    return record



def extract_specs(title):
    """Read explicit laptop specifications from a selected title, never recommendations."""
    specs = {}
    if re.search(r"\d+\s*GB\s*(?:/|or)\s*\d+\s*GB\s*(?:RAM|memory|SSD|storage)", title, re.I):
        raise ValueError("Product title describes multiple configurations; select one variant")
    patterns = {
        "ram_gb": r"\b(\d+)\s*GB\s*(?:(?:LP)?DDR[345]X?\s*)?(?:RAM|memory|unified memory)\b",
        "storage_gb": r"\b(\d+(?:\.\d+)?)\s*(GB|TB)\s*(?:SSD|storage|HDD)\b",
        "screen_inches": r'\b(\d+(?:\.\d+)?)\s*-?\s*(?:inch(?:es)?\b|in\b|")',
    }
    for key, pattern in patterns.items():
        matches = re.findall(pattern, title, re.I)
        values = set()
        for match in matches:
            if key == "storage_gb":
                number, unit = match
                values.add(float(number) * (1000 if unit.upper() == "TB" else 1))
            else:
                values.add(float(match))
        if len(values) > 1:
            raise ValueError(f"Conflicting {key} in selected product title")
        if values:
            value = values.pop()
            specs[key] = int(value) if value.is_integer() else value
    cpu_pattern = r"\b(?:Apple\s+)?M[1-9]\d*(?:\s+(?:Pro|Max|Ultra))?\b|\b(?:Intel\s+)?Core\s+i[3579]-\d{4,5}[A-Z]*\b|\b(?:AMD\s+)?Ryzen\s+[3579]\s+\d{4}[A-Z]*\b"
    from normalizer.matching import variant_key
    cpus = {variant_key("cpu", match.group(0)): match.group(0).strip() for match in re.finditer(cpu_pattern, title, re.I)}
    if len(cpus) > 1:
        raise ValueError("Conflicting CPU generations in selected product title")
    if cpus:
        specs["cpu"] = next(iter(cpus.values()))
    return specs


def merge_specs(explicit, title_specs):
    from normalizer.matching import variant_key
    result = dict(explicit)
    for key, value in title_specs.items():
        if key in result and variant_key(key, result[key]) != variant_key(key, value):
            raise ValueError(f"Conflicting {key} between product details and title")
        result.setdefault(key, value)
    return result


def fetch_page(url):
    return _guarded(_fetch_page, url)


def fetch_rendered_page(url, headless=True):
    return _guarded(lambda value: _fetch_rendered_page(value, headless=headless), url)


def reset_fetch_state():
    # begins a new explicit collection run after earlier access denials
    with _lock:
        BLOCKED_RETAILERS.clear()
        _last_request.clear()
