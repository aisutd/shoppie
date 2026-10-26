"""Read explicit, selected-product fields without title or whole-page guessing."""
import re
from decimal import Decimal, InvalidOperation

from scraper.diagnostics import ScraperFailure


def same_amount(left, right):
    try:
        left, right = Decimal(str(left)), Decimal(str(right))
        return left.is_finite() and right.is_finite() and left == right
    except InvalidOperation:
        return False


SPEC_LABELS = {
    "brand": {"brand"},
    "model": {"model", "model name", "item model number", "model number"},
    "cpu": {"cpu model", "processor", "processor model", "chip"},
    "ram": {"ram memory installed size", "ram", "ram size", "memory size"},
    "storage": {"hard disk size", "storage", "storage capacity", "hard drive size"},
    "screen_size": {"screen size", "standing screen display size", "display size"},
    "color": {"color", "colour"},
    "condition": {"condition", "item condition"},
}


def scalar(value):
    if isinstance(value, str):
        value = " ".join(value.replace("\u200e", "").replace("\u200f", "").split())
        return value if 0 < len(value) <= 300 else None
    return None


def selected_element(element):
    """Honor explicit visibility/offer selection, not CSS guesses or lowest price."""
    for node in (element, *element.parents):
        if not hasattr(node, "attrs"):
            continue
        classes = node.get("class", [])
        style = node.get("style", "")
        if (node.name in {"aside", "nav", "footer"} or "recommend" in node.get("aria-label", "").lower()
                or node.has_attr("hidden") or node.get("aria-hidden") == "true" or "aok-hidden" in classes
                or re.search(r"(?:^|;)\s*(?:display\s*:\s*none|visibility\s*:\s*hidden)\b", style, re.I)):
            return False
        if node.has_attr("data-a-accordion-row-name") and "a-accordion-active" not in classes:
            return False
    return True


def amazon_availability(soup):
    for selector in ("#availability .primary-availability-message", "#availability"):
        values = {node.get_text(" ", strip=True).lower().rstrip(".") for node in soup.select(selector)
                  if selected_element(node)}
        values.discard("")
        if len(values) == 1:
            value = next(iter(values))
            return {"in stock": "InStock", "out of stock": "OutOfStock",
                    "currently unavailable": "OutOfStock"}.get(value)
        if values:
            return None
    return None


def amazon_condition(soup):
    conditions = set()
    for row in soup.select('#buyBoxAccordion [data-a-accordion-row-name].a-accordion-active'):
        if not selected_element(row):
            continue
        heading = row.select_one('.a-accordion-row[aria-expanded="true"] h5')
        if heading:
            label = heading.get_text(" ", strip=True)
            if re.match(r"^Buy New\b", label):
                conditions.add("NewCondition")
            elif re.match(r"^Used\b", label):
                conditions.add("UsedCondition")
    if len(conditions) > 1:
        raise ValueError("Multiple selected Amazon offer conditions; no exact offer collected.")
    return next(iter(conditions), None)


def specifications(soup, retailer, product_id, product=None, offer=None):
    result = dict.fromkeys(SPEC_LABELS)
    values = {field: set() for field in SPEC_LABELS}
    def add(label, value):
        label, value = scalar(label), scalar(value)
        if not label or not value:
            return
        for field, labels in SPEC_LABELS.items():
            if label.lower() in labels:
                values[field].add(value)
    if product:
        brand = product.get("brand")
        add("brand", brand.get("name") if isinstance(brand, dict) else brand)
        for key, label in (("model", "model"), ("color", "color")):
            add(label, product.get(key))
        properties = product.get("additionalProperty", [])
        if isinstance(properties, dict):
            properties = [properties]
        if isinstance(properties, list):
            for prop in properties:
                if isinstance(prop, dict):
                    value = prop.get("value")
                    unit = scalar(prop.get("unitText"))
                    if unit and isinstance(value, (str, int, float)) and not isinstance(value, bool):
                        value = f"{value} {unit}"
                    add(prop.get("name"), value)
        if offer and isinstance(offer.get("itemCondition"), str):
            condition = offer["itemCondition"].rsplit("/", 1)[-1]
            if condition in {"NewCondition", "UsedCondition", "RefurbishedCondition", "DamagedCondition"}:
                add("condition", condition)
    if retailer == "amazon":
        add("condition", amazon_condition(soup))
        # Verified in live captures on 2026-10-26; never scan comparison tables.
        tables = soup.select("#productOverview_feature_div, #productDetails_techSpec_section_1, "
                             "#productDetails_techSpec_section_2, #productDetails_detailBullets_sections1")
        rows = []
        for table in tables:
            bound = table.get("data-csa-c-asin")
            if bound and bound != product_id:
                continue
            local = []
            for row in table.select("tr"):
                if row.find_parent(["aside", "nav", "footer"]):
                    continue
                cells = row.find_all(["th", "td"], recursive=False)
                if len(cells) == 2:
                    local.append((scalar(cells[0].get_text(" ", strip=True)), scalar(cells[1].get_text(" ", strip=True))))
            asins = {value for label, value in local if label and label.lower() == "asin"}
            if asins and asins != {product_id}:
                continue
            rows.extend(local)
        # A model number is more specific than a marketing model name.
        numbered = any(label and label.lower() in {"item model number", "model number"} for label, _ in rows)
        for label, value in rows:
            if numbered and label and label.lower() in {"model", "model name"}:
                continue
            add(label, value)
    for field, candidates in values.items():
        result[field] = next(iter(candidates)) if len(candidates) == 1 else None
    return result


def amazon_price(soup, product_id):
    """Require one exact main price, agreeing across duplicate primary modules."""
    soup = soup.select_one("#dp-container") or soup
    prices = set()
    for container in soup.select("#corePriceDisplay_desktop_feature_div, #corePrice_feature_div"):
        if not selected_element(container):
            continue
        if container.get("data-csa-c-asin") not in (None, product_id):
            raise ScraperFailure("Amazon main price belongs to a different ASIN.", "invalid_product_identity", stage="extraction")
        elements = container.select(".a-price.priceToPay, .a-price.apex-pricetopay-value")
        if not elements:
            elements = container.select(".a-price:not(.a-text-price)")
        for element in elements:
            # Secondary content can be nested even inside a main-price module.
            if not selected_element(element):
                continue
            offscreen = {tag.get_text(" ", strip=True) for tag in element.select(".a-offscreen")}
            offscreen.discard("")
            if len(offscreen) > 1:
                raise ValueError("Conflicting Amazon main-product price text.")
            displayed = next(iter(offscreen), None)
            if displayed is None:
                def part(selector):
                    tags = element.select(selector)
                    return tags[0].get_text("", strip=True) if len(tags) == 1 else ""
                symbol, whole, fraction = part(".a-price-symbol"), part(".a-price-whole"), part(".a-price-fraction")
                if re.fullmatch(r"(?:\d+|\d{1,3}(?:,\d{3})+)\.?", whole) and re.fullmatch(r"\d{2}", fraction):
                    displayed = symbol + whole.rstrip(".") + "." + fraction
            if displayed:
                if re.match(r"(?:CAD|CA\$|C\$|EUR|GBP|[€£¥])", displayed, re.I):
                    raise ScraperFailure("Amazon main-product price specifies a non-USD currency.", "invalid_currency", stage="extraction")
                match = re.fullmatch(r"(US\$|\$)?((?:\d+|\d{1,3}(?:,\d{3})+)\.\d{2})", displayed)
                if not match:
                    raise ValueError("Amazon main-product price is not one exact amount.")
                prices.add((match[2].replace(",", ""), "USD" if match[1] else None))
    if len(prices) > 1:
        raise ValueError("Conflicting Amazon main-product prices; no exact offer collected.")
    return next(iter(prices), (None, None))
