"""Retrieve public laptop pages and extract fields without database access."""

import json
import re
from contextlib import ExitStack
from datetime import datetime, timezone
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from scraper.diagnostics import ScraperFailure, browser_failure, request_failure
from scraper.product_fields import amazon_availability, amazon_condition, amazon_price, same_amount, specifications


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
    if re.search(r"\s", url):
        raise ValueError("Product URLs must not contain unescaped whitespace.")
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
    """Ignore only known tracking/display parameters; preserve offer/variant keys."""
    if identify_product(original) != identify_product(destination):
        return False
    harmless = {"sr", "ref", "ref_", "qid", "sprefix", "crid", "keywords", "s",
                "linkCode", "tag"}
    retailer, _ = identify_product(original)
    if retailer != "amazon":
        harmless = {"ref", "ref_"}
    if retailer == "target":
        # identify_product already resolves preselect to the child TCIN. A direct
        # child canonical URL encodes that same selection in its path instead.
        harmless.add("preselect")
    def selection(url):
        return {key: values for key, values in parse_qs(urlsplit(url).query, keep_blank_values=True).items()
                if key not in harmless and not key.lower().startswith("utm_")}
    return selection(original) == selection(destination)


def check_page(html):
    soup = BeautifulSoup(html, "html.parser")
    # Inspect visible text, not scripts that may merely mention a bot-check route.
    for tag in soup.select("script, style"):
        tag.decompose()
    lower = soup.get_text(" ", strip=True).lower()
    markers = ["robot check", "validatecaptcha", "verify you are human",
               "verify you're human", "press & hold", "access denied", "robot or human?",
               "sorry, we just need to make sure you're not a robot"]
    if any(marker in lower for marker in markers) or soup.select_one('input[name="captchacharacters"]'):
        raise ScraperFailure("Retailer returned a bot check or access-denied page. Stop here.", "challenge_or_access_denied")


def check_checkpoint_url(url):
    """Known live verification routes are terminal; never log their query tokens."""
    parts = urlsplit(url)
    if ((parts.hostname in {"walmart.com", "www.walmart.com"} and parts.path == "/blocked")
            or (parts.hostname in {"amazon.com", "www.amazon.com"} and parts.path == "/checkpoint/continue")):
        raise ScraperFailure("Retailer redirected to a verification/checkpoint page. Stop here.", "challenge_or_access_denied")


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
            check_checkpoint_url(destination)
            try:
                same_product = same_requested_product(url, destination)
            except ValueError:
                same_product = False
            if not same_product:
                raise ScraperFailure("Redirect left the requested product. Review its exact URL in your browser.", "redirect_identity_mismatch")
            url = clean_url(destination)
        else:
            raise ScraperFailure("Too many product-page redirects; no record collected.", "redirect_limit")
    except requests.RequestException as error:
        category, detail = request_failure(error)
        raise ScraperFailure("Page request failed or timed out; no record collected.", category, detail) from None
    # Only redirects within the same retailer AND product identity are followed.
    if response.status_code != 200:
        raise ScraperFailure(f"Retailer returned HTTP {response.status_code}; no record collected.", "http_status_error")
    if "text/html" not in response.headers.get("Content-Type", ""):
        raise ValueError("Expected an HTML product page.")
    check_page(response.text)
    return response.text


class BrowserSession:
    """Lazy batch browser reuse; each page keeps its own isolated context."""
    def __init__(self):
        self.stack = ExitStack()
        self.browser = None
        self.last_navigation = None

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.stack.close()

    def page(self):
        if self.browser is None:
            from playwright.sync_api import sync_playwright
            playwright = self.stack.enter_context(sync_playwright())
            self.browser = self.stack.enter_context(playwright.chromium.launch(channel="chrome", headless=True))
        return self.browser.new_page()


def fetch_rendered_page(url, session=None):
    """Render a selected product; retry one transport-protocol navigation failure."""
    if session is None:
        with BrowserSession() as session:
            return fetch_rendered_page(url, session)
    try:
        from playwright.sync_api import Error
    except ImportError:
        raise ScraperFailure("Install scraper/requirements.txt to use --browser.", "browser_launch_error") from None
    url = clean_url(url)
    session.last_navigation = None
    operation = "launch"
    page = None
    try:
        page = session.page()
        operation = "navigation"
        for navigation_attempt in range(2):
            try:
                response = page.goto(url, wait_until="domcontentloaded", timeout=30000)
                break
            except Error as error:
                if navigation_attempt == 0 and any(code in str(error) for code in (
                    "ERR_HTTP2_PROTOCOL_ERROR", "ERR_CONNECTION_RESET", "ERR_CONNECTION_CLOSED")):
                    # A fresh page/context, same normal Chrome settings; no evasion.
                    page.close()
                    page = session.page()
                    continue
                raise
        if response is None or response.status != 200:
            detail = "Chrome navigation returned no response." if response is None else f"Chrome received HTTP {response.status}."
            raise ScraperFailure("Browser did not receive a successful product page.", "http_status_error", detail)
        operation = "readiness"
        for attempt in range(10):
            html = page.content()
            check_page(html)
            check_checkpoint_url(page.url)
            try:
                same_product = same_requested_product(url, page.url)
            except ValueError:
                same_product = False
            if not same_product:
                raise ScraperFailure("Browser redirected away from the requested product. Review the URL in your browser.", "redirect_identity_mismatch")
            try:
                candidate = extract_product(html, url)
            except ScraperFailure:
                raise
            except ValueError as error:
                raise ScraperFailure(str(error), "extraction_failed", "Product extraction rejected a browser readiness snapshot.", stage="extraction") from None
            if candidate["title"] and candidate["price"] is not None and candidate["currency"]:
                break
            visible = BeautifulSoup(html, "html.parser")
            for tag in visible.select("script, style"):
                tag.decompose()
            if "there was a temporary issue" in visible.get_text(" ", strip=True).lower():
                raise ScraperFailure("Target reported a temporary product-data issue; price/currency were not supplied. Try the real page again later.", "source_data_unavailable")
            if attempt < 9:
                page.wait_for_timeout(2000)
        else:
            missing = [name for name in ("title", "price", "currency") if not candidate[name]]
            raise ScraperFailure("Browser product readiness timed out; missing " + ", ".join(missing) + ". No record collected.", "readiness_timeout")
        # Same snapshot and same identity are used for extraction and readiness.
        check_page(html)
        if not same_requested_product(url, page.url):
            raise ScraperFailure("Browser redirected away from the requested product. Review the URL in your browser.", "redirect_identity_mismatch")
        session.last_navigation = dict(requested_url=url, final_url=page.url, status=response.status,
                                       navigation_retries=navigation_attempt)
        return html
    except Error as error:
        category, detail = browser_failure(error, operation)
        raise ScraperFailure("Browser load failed, timed out, or closed. Check Chrome and network access.", category, detail) from None
    finally:
        if page is not None:
            try:
                page.close()
            except Error:
                pass


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
        if len(products) == 1 and (products[0].get("url") or products[0].get("@id")):
            try:
                other_identity = identify_product(urljoin(url, products[0].get("url") or products[0]["@id"]))
            except (ValueError, TypeError):
                other_identity = None
            if other_identity is not None and other_identity != identity:
                raise ScraperFailure("Cannot safely identify one main Product: JSON-LD identifies another product.",
                                     "invalid_product_identity", stage="extraction")
        raise ValueError("Cannot safely identify one main Product in the page JSON-LD.")
    return None


def text(soup, selector):
    tags = soup.select(selector)
    # Conflicting matches cannot establish one main-product value.
    values = {tag.get_text(" ", strip=True) for tag in tags}
    return next(iter(values)) if len(values) == 1 else None


def meta(soup, field):
    # Page-level product metadata describes this page. Unscoped itemprop tags
    # can belong to a recommendation; never mix them into the main title.
    if soup.head is None:
        return None
    values = {tag.get("content") for tag in soup.head.select(f'meta[property="product:{field}"]')}
    return next(iter(values)) if len(values) == 1 else None


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


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    # Refuse a different selected product (for example an Amazon variant change).
    canonical = soup.select_one('link[rel="canonical"]')
    if canonical and canonical.get("href"):
        if identify_product(urljoin(url, canonical["href"])) != (retailer, product_id):
            raise ScraperFailure("Page canonical URL identifies a different product.", "invalid_product_identity", stage="extraction")
    if retailer == "amazon":
        asin = soup.select_one('input#ASIN')
        if asin and asin.get("value") and asin["value"] != product_id:
            raise ScraperFailure("Amazon selected a different ASIN; use that product's exact URL.", "invalid_product_identity", stage="extraction")
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
                raise ScraperFailure("Offer belongs to a different product; no price collected.", "invalid_product_identity", stage="extraction")
        record["price"] = offers.get("price")
        record["currency"] = offers.get("priceCurrency")
        record["availability"] = offers.get("availability")
        seller = offers.get("seller")
        record["seller"] = seller.get("name") if isinstance(seller, dict) else None
        if retailer == "amazon" and isinstance(offers.get("itemCondition"), str):
            selected_condition = amazon_condition(soup)
            if selected_condition and offers["itemCondition"].rsplit("/", 1)[-1] != selected_condition:
                raise ScraperFailure("Amazon structured Offer condition does not match the selected offer.",
                                     "invalid_product_identity", stage="extraction")
        record.update(specifications(soup, retailer, product_id, product, offers))
        if retailer == "amazon":
            displayed_price, displayed_currency = amazon_price(soup, product_id)
            if record["price"] is None:
                record["price"] = displayed_price
            elif displayed_price is not None and not same_amount(record["price"], displayed_price):
                raise ValueError("Amazon structured and displayed main-product prices disagree.")
            if record["currency"] is not None and displayed_currency and record["currency"] != displayed_currency:
                raise ScraperFailure("Amazon structured and displayed main-product currencies disagree.", "invalid_currency", stage="extraction")
            if record["currency"] is None and displayed_currency and same_amount(record["price"], displayed_price):
                record["currency"] = displayed_currency
        return record

    # These fallbacks only inspect the main product's named HTML elements.
    # No whole-page price regex: it could pick a monthly payment or accessory.
    titles = {
        "amazon": "span#productTitle, h1#productTitle", "bestbuy": "h1",
        "target": 'h1[data-test="product-title"], h1',
        "walmart": 'h1[itemprop="name"], h1',
    }
    # Recommendations may reuse the same price attributes. Limit HTML fields
    # to main content and exclude secondary regions even when nested in main.
    context = (soup.select_one("#dp-container") if retailer == "amazon" else None) or soup.select_one("main") or soup
    for secondary in context.select('aside, nav, footer, [aria-label*="recommend" i]'):
        secondary.decompose()
    record["title"] = text(context, titles[retailer])
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
        displayed = text(context, price_selectors[retailer])
        # Match only a single whole price in the named main-product price element.
        if displayed and re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
            record["price"] = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            if displayed.startswith("US$"):
                record["currency"] = "USD"
    if retailer == "amazon":
        displayed_price, displayed_currency = amazon_price(context, product_id)
        if displayed_price is not None:
            if record["price"] is not None and not same_amount(record["price"], displayed_price):
                raise ValueError("Amazon metadata and displayed main-product price disagree.")
            if record["currency"] is not None and displayed_currency and record["currency"] != displayed_currency:
                raise ScraperFailure("Amazon metadata and displayed main-product currency disagree.", "invalid_currency", stage="extraction")
            record["price"] = displayed_price
            record["currency"] = displayed_currency or record["currency"]
        if record["availability"] is None:
            record["availability"] = amazon_availability(context)
    record.update(specifications(soup, retailer, product_id))
    return record

