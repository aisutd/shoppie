"""Retrieve public laptop pages and extract fields without database access."""

import json
import re
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup


PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    "walmart": r"/ip/(?:[^/]+/)?(\d+)(?:/|$)",
}


def identify_product(url):
    """Accept only HTTPS product URLs at our four US retailers."""
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


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    # Inspect visible text, not scripts that may merely mention a bot-check route.
    for tag in soup.select("script, style"):
        tag.decompose()
    lower = soup.get_text(" ", strip=True).lower()
    markers = ["robot check", "validatecaptcha", "verify you are human",
               "verify you're human", "press & hold", "access denied"]
    if any(marker in lower for marker in markers) or soup.select_one('input[name="captchacharacters"]'):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")


def fetch_page(url):
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
    if response.status_code != 200:
        raise ValueError(f"Retailer returned HTTP {response.status_code}; no record collected.")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
    check_page(response.text)
    return response.text


def fetch_rendered_page(url):
    """Optional Chrome rendering for JavaScript-rendered product pages."""
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise ValueError("Install scraper/requirements.txt to use --browser.") from None
    url = clean_url(url)
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(channel="chrome", headless=True) as browser:
                page = browser.new_page()
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                if response is None or response.status != 200:
                    raise ValueError("Browser did not receive a successful product page.")
                # Observe readiness instead of assuming scripts finish in five seconds.
                # A challenge is terminal; never solve or work around it.
                for attempt in range(10):
                    html = page.content()
                    check_page(html)
                    candidate = extract_product(html, url)
                    if candidate["title"] and candidate["price"] is not None and candidate["currency"]:
                        break
                    visible = BeautifulSoup(html, "html.parser")
                    for tag in visible.select("script, style"):
                        tag.decompose()
                    if "there was a temporary issue" in visible.get_text(" ", strip=True).lower():
                        raise ValueError("Target reported a temporary product-data issue; price/currency were not supplied. Try the real page again later.")
                    page.wait_for_timeout(2000)
                html = page.content()
                check_page(html)
                try:
                    same_product = same_requested_product(url, page.url)
                except ValueError:
                    same_product = False
                if not same_product:
                    raise ValueError("Browser redirected away from the requested product. Review the URL in your browser.")
    except Error:
        raise ValueError("Browser load failed, timed out, or closed. Check Chrome and network access.") from None
    check_page(html)
    return html


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


def target_embedded_title(soup, product_id):
    """Read only Target layout title modules explicitly bound to this TCIN.

    Verified in the real 91122087 page's __NEXT_DATA__ on 2026-10-14.
    Do not recursively search arbitrary JSON for prices or recommendation titles.
    """
    script = soup.select_one('script#__NEXT_DATA__[type="application/json"]')
    if script is None:
        return None
    try:
        queries = json.loads(script.get_text())["props"]["dehydratedState"]["queries"]
        titles = set()
        for query in queries:
            payload = query.get("state", {}).get("data") or {}
            layout = (payload.get("data") or {}).get("layout") or {}
            for zone in layout.get("zones", []):
                for group in zone.get("module_groups", []):
                    for module in group.get("modules", []):
                        for item in module.get("module_data", {}).get("data_by_tcin", []):
                            title = item.get("title")
                            if item.get("tcin") == product_id and isinstance(title, str) and title.strip():
                                titles.add(title.strip())
    except (ValueError, KeyError, TypeError, AttributeError):
        return None
    if len(titles) > 1:
        raise ValueError("Target embedded data contains conflicting titles for the selected variant.")
    return next(iter(titles), None)


def amazon_page_fields(soup):
    """Read Amazon's product title and primary offer from product-specific areas."""
    title = text(soup, "#productTitle, #title_feature_div #title")
    if not title:
        # Open Graph title is page-scoped metadata, unlike recommendation cards.
        tag = soup.select_one('meta[property="og:title"]')
        value = tag.get("content", "").strip() if tag else ""
        if value and value.lower() not in {"amazon.com", "amazon"}:
            title = value

    price = currency = availability = None
    containers = soup.select(
        "#corePriceDisplay_desktop_feature_div, #corePrice_feature_div, "
        "#apex_desktop, #buybox"
    )
    # Amazon also publishes the selected currency in its navigation's
    # currencyInfo, even when the primary offer markup omits priceCurrency.
    # Use that explicit page setting only alongside a price from the product area.
    page_currency = None
    for script in soup.find_all("script"):
        script_text = script.string or script.get_text()
        match = re.search(
            r'"currencyInfo"\s*:\s*\{\s*"code"\s*:\s*"([A-Z]{3})"',
            script_text,
        )
        if match:
            page_currency = match.group(1)
            break
    for container in containers:
        currency_tag = container.select_one('[itemprop="priceCurrency"], [data-a-currency-code]')
        if currency_tag:
            currency = currency_tag.get("content") or currency_tag.get("data-a-currency-code")
        if price is None:
            price_tag = container.select_one(
                '.a-price:not(.a-text-price) .a-offscreen, '
                '#priceblock_ourprice, #priceblock_dealprice, #priceblock_saleprice'
            )
            if price_tag:
                displayed = price_tag.get("content") or price_tag.get_text(" ", strip=True)
                match = re.fullmatch(
                    r"\s*(US\$|\$)?\s*((?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{2})?)\s*",
                    displayed,
                )
                if match:
                    symbol, amount = match.groups()
                    price = amount.replace(",", "")
                    # A bare dollar sign does not establish currency.
                    if symbol == "US$":
                        currency = currency or "USD"
        if availability is None:
            availability_tag = container.select_one('[itemprop="availability"]')
            if availability_tag:
                availability = availability_tag.get("href") or availability_tag.get_text(" ", strip=True)
    if price is not None and currency is None:
        currency = page_currency
    return title, price, currency, availability


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    # Refuse a different selected product (for example an Amazon variant change).
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get("href"):
        if identify_product(urljoin(url, canonical["href"])) != (retailer, product_id):
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
            if not isinstance(offers["url"], str) or identify_product(urljoin(url, offers["url"])) != (retailer, product_id):
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
        title, price, currency, availability = amazon_page_fields(soup)
        record["title"] = record["title"] or title
        record["price"] = record["price"] or price
        record["currency"] = record["currency"] or currency
        record["availability"] = record["availability"] or availability
    return record

