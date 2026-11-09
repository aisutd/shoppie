"""Retrieve public laptop pages and extract fields without database access."""

import json
import re
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from urllib.parse import parse_qs, urljoin, urlsplit

import requests
from bs4 import BeautifulSoup

from scraper.product_access import USER_AGENT, require_product_access

PRODUCT_PATHS = {
    "amazon": r"/(?:dp|gp/product)/([A-Z0-9]{10})(?:/|$)",
    "bestbuy": r"/(?:site/.+/(\d+)\.p|product/[^/]+/([A-Z0-9]+))(?:/|$)",
    "target": r"/p/.*/A-(\d+)(?:/|$)",
    "walmart": r"/ip/(?:[^/]+/)?(\d+)(?:/|$)",
}


def identify_product(url):
    """Accept only HTTPS product URLs at our four US retailers."""
    if not isinstance(url, str) or any(c.isspace() for c in url):
        raise ValueError("Malformed product URL.")
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
               "verify you're human", "press & hold", "access denied",
               "click the button below to continue shopping", "enter the characters you see below",
               "verify you are a human", "verify you're a human", "too many requests"]
    if (any(marker in lower for marker in markers)
            or soup.select_one('input[name="captchacharacters"]')
            or soup.select_one('form[action*="validateCaptcha"]')):
        raise ValueError("Retailer returned a bot check or access-denied page. Stop here.")


def fetch_page(url):
    url = clean_url(url)
    retailer, _ = identify_product(url)
    rules = {}
    try:
        for attempt in range(4):
            if retailer in {"target", "amazon"}:
                require_product_access(url, rules)
            response = requests.get(
                url, timeout=25, allow_redirects=False,
                headers={"User-Agent": USER_AGENT},
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


def fetch_rendered_page(url, headless=True):
    """Optional Chromium rendering for JavaScript-rendered product pages."""
    try:
        from playwright.sync_api import sync_playwright, Error
    except ImportError:
        raise ValueError("Install scraper/requirements.txt to use --browser.") from None
    url = clean_url(url)
    try:
        with sync_playwright() as playwright:
            with playwright.chromium.launch(headless=headless) as browser:
                retailer, _ = identify_product(url)
                page = browser.new_page(user_agent=USER_AGENT) if retailer in {"target", "amazon"} else browser.new_page()
                if retailer in {"target", "amazon"}:
                    require_product_access(url, {})

                    def guard_navigation(route):
                        request = route.request
                        if request.is_navigation_request() and request.frame == page.main_frame:
                            if request.url != url:
                                route.abort()
                                return
                            # inspects the original response without following a redirect
                            response = route.fetch(max_redirects=0, timeout=30000)
                            if response.status != 200:
                                route.abort()
                                return
                            route.fulfill(response=response)
                        else:
                            route.continue_()

                    page.route("**/*", guard_navigation)
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


def matching_reference(url, reference):
    destination = urljoin(url, reference)
    identity = identify_product(url)
    if identify_product(destination) != identity:
        return False
    query = urlsplit(destination).query
    return identity[0] not in {"target", "amazon"} or not query or query == urlsplit(url).query


def main_product(soup, url):
    products = []
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            products.extend(product_nodes(json.loads(script.get_text())))
        except (ValueError, TypeError):
            continue
    matches = []
    for product in products:
        reference = product.get("url") or product.get("@id")
        if isinstance(reference, str):
            try:
                if matching_reference(url, reference):
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


def agreed_value(values, field):
    values = [value for value in values if value not in (None, "")]
    if not values:
        return None
    if field == "price":
        try:
            distinct = {Decimal(str(value).replace(",", "")) for value in values}
        except InvalidOperation:
            raise ValueError("Invalid selected product price") from None
        if any(not value.is_finite() for value in distinct):
            raise ValueError("Invalid selected product price")
    elif field == "availability":
        distinct = {re.sub(r"[\s_-]+", "", str(value).rsplit("/", 1)[-1].casefold()) for value in values}
    else:
        distinct = {" ".join(str(value).split()).casefold() for value in values}
    if len(distinct) != 1:
        raise ValueError(f"Conflicting {field} for the selected product")
    return values[0]


def target_embedded_fields(soup, product_id):
    # only reads Target layout data bound to the selected TCIN
    script = soup.select_one('script#__NEXT_DATA__[type="application/json"]')
    fields = {key: [] for key in ("title", "price", "currency")}
    if script is None:
        return {}
    try:
        queries = json.loads(script.get_text())["props"]["dehydratedState"]["queries"]
        for query in queries:
            payload = query.get("state", {}).get("data") or {}
            layout = (payload.get("data") or {}).get("layout") or {}
            for zone in layout.get("zones", []):
                for group in zone.get("module_groups", []):
                    for module in group.get("modules", []):
                        for item in module.get("module_data", {}).get("data_by_tcin", []):
                            if str(item.get("tcin")) != product_id:
                                continue
                            if isinstance(item.get("title"), str):
                                fields["title"].append(item["title"].strip())
                            price = item.get("price")
                            if isinstance(price, dict):
                                fields["price"].append(price.get("current_retail"))
                                fields["currency"].append(price.get("currency") or price.get("priceCurrency"))
    except (ValueError, KeyError, TypeError, AttributeError):
        return {}
    return {key: agreed_value(values, key) for key, values in fields.items()}


def amazon_page_fields(soup):
    """Read Amazon's product title and primary offer from product-specific areas."""
    title = text(soup, "#productTitle, #title_feature_div #title")
    if not title:
        # Open Graph title is page-scoped metadata, unlike recommendation cards.
        tag = soup.select_one('meta[property="og:title"]')
        value = tag.get("content", "").strip() if tag else ""
        if value and value.lower() not in {"amazon.com", "amazon"}:
            title = value

    prices, currencies, availability = [], [], None
    for container in soup.select("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div, #apex_desktop, #buybox"):
        price_tags = container.select(
            '.a-price:not(.a-text-price) .a-offscreen, '
            '#priceblock_ourprice, #priceblock_dealprice, #priceblock_saleprice'
        )
        for tag in price_tags:
            displayed = tag.get("content") or tag.get_text(" ", strip=True)
            match = re.fullmatch(r"\s*(US\$|\$)?\s*((?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{2})?)\s*", displayed)
            if match:
                symbol, amount = match.groups()
                prices.append(amount.replace(",", ""))
                if symbol == "US$":
                    currencies.append("USD")
        for tag in container.select('[itemprop="priceCurrency"], [data-a-currency-code]'):
            currencies.append(tag.get("content") or tag.get("data-a-currency-code"))
        stock = container.select_one('[itemprop="availability"]')
        if stock:
            availability = agreed_value([availability, stock.get("href") or stock.get("content") or stock.get_text(" ", strip=True)], "availability")
    status = text(soup, "#availability")
    if status and status.strip(" .").lower() in {"currently unavailable", "out of stock", "sold out"}:
        availability = agreed_value([availability, "OutOfStock"], "availability")
    if prices:
        # amazon's explicit page currency can accompany a primary offer amount
        for script in soup.find_all("script"):
            currencies.extend(re.findall(r'"currencyInfo"\s*:\s*\{\s*"code"\s*:\s*"([A-Z]{3})"', script.string or script.get_text()))
    return title, agreed_value(prices, "price"), agreed_value(currencies, "currency"), availability


def selected_page_fields(soup, retailer):
    # compares only named product metadata and the retailer's primary offer
    prices = [meta(soup, "price:amount"), meta(soup, "price")]
    currencies = [meta(soup, "price:currency"), meta(soup, "priceCurrency")]
    availability = [meta(soup, "availability")]
    title = None
    if retailer == "amazon":
        title, price, currency, stock = amazon_page_fields(soup)
        prices.append(price)
        currencies.append(currency)
        availability.append(stock)
    else:
        for tag in soup.select('[data-test="product-price"]'):
            displayed = tag.get_text(" ", strip=True)
            if re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
                prices.append(re.sub(r"^(US\$|\$)", "", displayed).replace(",", ""))
                if displayed.startswith("US$"):
                    currencies.append("USD")
    return {"title": title, "price": agreed_value(prices, "price"),
            "currency": agreed_value(currencies, "currency"),
            "availability": agreed_value(availability, "availability")}


def extract_product(html, url):
    check_page(html)
    url = clean_url(url)
    retailer, product_id = identify_product(url)
    soup = BeautifulSoup(html, "html.parser")
    # checks canonical identity before trusting page-level fields
    canonical = soup.select_one('link[rel="canonical"][href]')
    target_variant = retailer == "target" and "preselect" in parse_qs(urlsplit(url).query)
    canonical_matches = canonical and matching_reference(url, canonical["href"])
    if canonical and not canonical_matches:
        parent_url = urlsplit(url)._replace(query="").geturl()
        parent_identity = identify_product(parent_url)
        if not target_variant or identify_product(urljoin(url, canonical["href"])) != parent_identity:
            raise ValueError("Page canonical URL identifies a different product.")
    if retailer == "amazon":
        asins = {tag["value"] for tag in soup.select('input#ASIN[value]') if tag["value"]}
        if asins and asins != {product_id}:
            raise ValueError("Amazon selected a different ASIN; use that product's exact URL.")
    record = {
        "retailer": retailer, "product_id": product_id, "product_url": url,
        "title": None, "price": None, "currency": None, "availability": None,
        "seller": None, "discount": None, "image_url": None,
        "observed_at": datetime.now(timezone.utc).isoformat(),
        "extraction_method": "html",
    }
    product = main_product(soup, url)
    # parent-level artwork and description cannot identify a selected child
    use_page_fields = not target_variant or bool(canonical_matches)
    record["image_url"] = product_image_url(soup if use_page_fields else None, product, url)
    description = product.get("description") if product else None
    if not isinstance(description, str) or not description.strip():
        tag = soup.select_one('meta[property="og:description"], meta[name="description"]')
        description = tag.get("content") if tag and use_page_fields else None
    if description:
        record["description"] = BeautifulSoup(description, "html.parser").get_text(" ", strip=True) or None
    target_fields = target_embedded_fields(soup, product_id) if retailer == "target" else {}
    if target_variant and not canonical_matches:
        product_reference = product and (product.get("url") or product.get("@id"))
        if not product_reference:
            if not target_fields.get("title"):
                raise ValueError("Target page does not identify the selected variant")
            # unbound page metadata could describe the parent variant
            record.update(target_fields, image_url=None, description=None)
            return record
    page_fields = selected_page_fields(soup, retailer) if retailer in {"target", "amazon"} and use_page_fields else {}
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
            if not isinstance(offers["url"], str) or not matching_reference(url, offers["url"]):
                raise ValueError("Offer belongs to a different product; no price collected.")
        record["price"] = offers.get("price")
        record["currency"] = offers.get("priceCurrency")
        record["availability"] = offers.get("availability")
        seller = offers.get("seller")
        record["seller"] = seller.get("name") if isinstance(seller, dict) else None
        if retailer in {"target", "amazon"}:
            record["title"] = agreed_value([record["title"], target_fields.get("title"), page_fields.get("title")], "title")
            spec = offers.get("priceSpecification")
            if isinstance(spec, list) and len(spec) == 1:
                spec = spec[0]
            if spec is not None and not isinstance(spec, dict):
                raise ValueError("Expected one exact price specification")
            spec = spec or {}
            if any(key in spec for key in ("billingDuration", "billingIncrement", "referenceQuantity", "priceType")):
                raise ValueError("Expected a current product price, not a pricing schedule")
            for field, key in (("price", "price"), ("currency", "priceCurrency")):
                record[field] = agreed_value([record[field], spec.get(key), target_fields.get(field), page_fields.get(field)], field)
            record["availability"] = agreed_value([record["availability"], page_fields.get("availability")], "availability")
        return record

    # These fallbacks only inspect the main product's named HTML elements.
    # No whole-page price regex: it could pick a monthly payment or accessory.
    titles = {
        "amazon": "#productTitle", "bestbuy": "h1",
        "target": 'h1[data-test="product-title"], h1',
        "walmart": 'h1[itemprop="name"], h1',
    }
    record["title"] = text(soup, titles[retailer])
    if retailer in {"target", "amazon"}:
        for field in ("title", "price", "currency", "availability"):
            record[field] = agreed_value([record[field], target_fields.get(field), page_fields.get(field)], field)
        return record

    record["price"] = meta(soup, "price:amount") or meta(soup, "price")
    record["currency"] = meta(soup, "price:currency") or meta(soup, "priceCurrency")
    record["availability"] = meta(soup, "availability")
    if retailer == "bestbuy" and record["price"] is None:
        displayed = text(soup, '[data-testid="customer-price"]')
        if displayed and re.fullmatch(r"(?:US\$|\$)?(?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2}", displayed):
            record["price"] = re.sub(r"^(US\$|\$)", "", displayed).replace(",", "")
            if displayed.startswith("US$"):
                record["currency"] = "USD"
    return record


def product_image_url(soup, product, page_url):
    candidates = []

    def add_json_image(value):
        if isinstance(value, str):
            candidates.append(value)
        elif isinstance(value, list):
            for item in value:
                add_json_image(item)
        elif isinstance(value, dict):
            for key in ("url", "contentUrl", "thumbnailUrl"):
                if value.get(key):
                    add_json_image(value[key])

    if product:
        add_json_image(product.get("image"))

    for selector in (
        'meta[property="og:image"]',
        'meta[property="og:image:secure_url"]',
        'meta[name="twitter:image"]',
    ):
        tag = soup.select_one(selector) if soup is not None else None
        if tag and tag.get("content"):
            candidates.append(tag["content"])

    for selector in (
        "#landingImage",
        'img[itemprop="image"]',
        '[data-test*="product-image"] img',
        '[data-testid*="hero"] img',
        "main img",
    ):
        image = soup.select_one(selector) if soup is not None else None
        if not image:
            continue
        for attribute in ("data-src", "data-original", "src", "data-srcset", "srcset"):
            value = image.get(attribute)
            if value:
                candidates.append(value.split(",")[0].strip().split()[0])

    for candidate in candidates:
        try:
            resolved = urljoin(page_url, candidate.strip())
            parts = urlsplit(resolved)
            if parts.scheme == "https" and parts.hostname and not parts.username and not parts.password:
                return resolved
        except (AttributeError, ValueError):
            continue
    return None
