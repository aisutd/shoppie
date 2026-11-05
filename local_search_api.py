"""Local-only product search API backed by Ollama and the Supabase products table."""

import json
import logging
import math
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from scraper.config import ConfigurationError, load_database_config
from scraper.live_search import CollectedProduct, collect_live_products, infer_category
from scraper.bestbuy_search import DiscoveryError, discover_bestbuy_products
from scraper.walmart_search import WalmartDiscoveryError, discover_walmart_products
from scraper.search_intent import apply_requirements, listing_type, parse_requirements, product_type


HOST = "127.0.0.1"
PORT = 8001
logger = logging.getLogger(__name__)
OLLAMA_URL = "http://127.0.0.1:11434/api/chat"
MODEL = "qwen2.5-coder:1.5b"
MAX_BODY_BYTES = 8_192
CATALOG_CACHE_SECONDS = 300
CATALOG_PAGE_SIZE = 500
MAX_RESULTS = 60
FUZZY_TOKEN_THRESHOLD = 0.72
SEARCH_STOP_WORDS = {
    "a", "an", "and", "at", "best", "find", "for", "get", "give",
    "good", "in", "least", "looking", "me", "my", "need", "of", "on", "please",
    "recommend", "search", "show", "suggest", "the", "to", "want", "with",
}
HOMEPAGE_SEARCHES = (
    "laptop",
    "monitor",
    "cell phone",
    "headphones",
    "gaming controller",
    "toys",
    "coffee mug",
)
HOMEPAGE_CATEGORIES = {
    "laptop": "laptops",
    "monitor": "monitors",
    "cell phone": "phones",
    "headphones": "headphones",
    "gaming controller": "gaming",
    "toys": "toys-games",
    "coffee mug": "kitchen-dining",
}
PRICE_AMOUNT = r"\$?\s*((?:\d{1,3}(?:,\d{3})+|\d+)(?:\.\d{1,2})?)\s*(?:dollars?|usd)?"
_catalog_cache = {"expires_at": 0, "products": []}
_catalog_lock = threading.Lock()


def interpret_query(query):
    response = requests.post(
        OLLAMA_URL,
        json={
            "model": MODEL,
            "stream": False,
            "format": "json",
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "Turn a shopping search into useful product database search terms. "
                        'Return JSON only as {"terms":["term", ...]}. Include the key product '
                        "type and up to four specific synonyms or attributes. Do not answer the user."
                    ),
                },
                {"role": "user", "content": query},
            ],
            "options": {"temperature": 0},
        },
        timeout=90,
    )
    response.raise_for_status()
    message = response.json().get("message", {}).get("content", "")
    parsed = json.loads(message)
    terms = parsed.get("terms", [])
    if not isinstance(terms, list):
        raise ValueError("The local model returned an invalid search response.")

    safe_terms = []
    for term in terms:
        if not isinstance(term, str):
            continue
        term = re.sub(r"[^a-zA-Z0-9 -]", " ", term).strip()[:60]
        if term and term.casefold() not in {item.casefold() for item in safe_terms}:
            safe_terms.append(term)
        if len(safe_terms) == 5:
            break
    if not safe_terms:
        raise ValueError("The local model did not return any search terms.")
    return safe_terms


def load_catalog(database):
    """Load a pageable snapshot of the product catalog, cached for five minutes."""
    now = time.monotonic()
    if _catalog_cache["expires_at"] > now:
        return _catalog_cache["products"]

    with _catalog_lock:
        now = time.monotonic()
        if _catalog_cache["expires_at"] > now:
            return _catalog_cache["products"]

        products = []
        offset = 0
        while True:
            result = requests.get(
                f"{database.url}/rest/v1/products",
                headers={
                    "apikey": database.secret_key,
                    "Authorization": f"Bearer {database.secret_key}",
                },
                params={
                    "select": "id,title,description,image_url,price,currency,product_url,source,category,scraped_at",
                    "order": "id.asc",
                    "limit": str(CATALOG_PAGE_SIZE),
                    "offset": str(offset),
                },
                timeout=20,
            )
            result.raise_for_status()
            page = result.json()
            products.extend(page)
            if len(page) < CATALOG_PAGE_SIZE:
                break
            offset += CATALOG_PAGE_SIZE

        _catalog_cache["products"] = products
        _catalog_cache["expires_at"] = time.monotonic() + CATALOG_CACHE_SECONDS
        return products


def correct_legacy_categories(products):
    """Replace the old catch-all electronics label when title evidence disagrees."""
    return [
        {
            **product,
            "category": infer_category(product.get("title"))
            if product.get("category") == "electronics"
            else product.get("category"),
        }
        for product in products
    ]


def deal_collections(products, bestbuy_products=(), walmart_products=()):
    """Build homepage groups from the catalog and verified retailer offers."""
    products = correct_legacy_categories(products)
    priced_products = []
    for product in products:
        try:
            price = Decimal(str(product["price"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            continue
        if price.is_finite() and price > 0:
            priced_products.append((price, product))

    lowest_prices = [
        product for _, product in sorted(
            priced_products, key=lambda item: (item[0], item[1].get("title", "").casefold())
        )[:6]
    ]

    def observed_timestamp(product):
        observed_at = product.get("scraped_at")
        if not isinstance(observed_at, str):
            return float("-inf")
        try:
            parsed = datetime.fromisoformat(observed_at.replace("Z", "+00:00"))
            if parsed.tzinfo is None:
                parsed = parsed.replace(tzinfo=timezone.utc)
            return parsed.timestamp()
        except ValueError:
            return float("-inf")

    newest_observations = sorted(
        products, key=observed_timestamp, reverse=True
    )[:6]
    live_products = [*bestbuy_products, *walmart_products]
    discounted_products = []
    for product in live_products:
        try:
            current_price = Decimal(str(product["price"]))
            regular_price = Decimal(str(product["regular_price"]))
        except (KeyError, InvalidOperation, TypeError, ValueError):
            continue
        if (
            current_price.is_finite()
            and regular_price.is_finite()
            and regular_price > current_price > 0
        ):
            discounted_products.append(
                {
                    **product,
                    "savings_percent": round(
                        float((regular_price - current_price) / regular_price * 100),
                        1,
                    ),
                }
            )
    discounted_products.sort(
        key=lambda product: (
            -product["savings_percent"],
            product["title"].casefold(),
        )
    )
    return [
        {"id": "all-time-lows", "products": lowest_prices},
        {"id": "deep-discounts", "products": discounted_products[:12]},
        {"id": "new-releases", "products": newest_observations},
        {"id": "bestbuy-picks", "products": list(bestbuy_products)},
        {"id": "walmart-picks", "products": list(walmart_products)},
    ]


def discover_homepage_products():
    """Collect a bounded spread of current products from both retailers."""
    searches = []
    for query in HOMEPAGE_SEARCHES:
        searches.append(("bestbuy.com", query))
        searches.append(("walmart.com", query))

    errors = []

    def discover(search):
        source, query = search
        try:
            if source == "bestbuy.com":
                products = discover_bestbuy_products(query, limit=4)
            else:
                products = discover_walmart_products(query, limit=4)
            return source, query, products, None
        except (DiscoveryError, WalmartDiscoveryError) as error:
            logger.warning(
                "%s homepage discovery for %s failed (%s)",
                source,
                query,
                error.code,
            )
            return source, query, [], str(error)

    by_retailer = {"bestbuy.com": [], "walmart.com": []}
    seen_urls = set()
    with ThreadPoolExecutor(max_workers=6) as pool:
        for source, query, products, error in pool.map(discover, searches):
            if error:
                errors.append(f"{source} ({query}): {error}")
            for product in products:
                url = product["product_url"]
                if url in seen_urls:
                    continue
                seen_urls.add(url)
                category = infer_category(product["title"])
                product["category"] = (
                    HOMEPAGE_CATEGORIES[query]
                    if category == "other"
                    else category
                )
                by_retailer[source].append(product)

    return by_retailer["bestbuy.com"], by_retailer["walmart.com"], errors


def validate_retailer_products(products):
    """Validate live homepage records while retaining verified compare prices."""
    validated = []
    for product in products:
        record = CollectedProduct.model_validate(product).model_dump(mode="json")
        try:
            regular_price = Decimal(str(product.get("regular_price")))
            current_price = Decimal(str(record["price"]))
        except (InvalidOperation, TypeError, ValueError):
            regular_price = None
            current_price = None
        if (
            regular_price is not None
            and regular_price.is_finite()
            and current_price is not None
            and regular_price > current_price
        ):
            record["regular_price"] = format(regular_price, ".2f")
        validated.append(record)
    return validated


def normalize_tokens(value):
    tokens = re.findall(r"[a-z0-9]+", str(value or "").casefold())
    unit_aliases = {
        "gigabyte": "gb", "gigabytes": "gb", "gib": "gb",
        "megabyte": "mb", "megabytes": "mb", "mib": "mb",
        "terabyte": "tb", "terabytes": "tb", "tib": "tb",
        "ram": "memory",
    }
    normalized = []
    for token in tokens:
        measurement = re.fullmatch(r"(\d+)(gb|gib|mb|mib|tb|tib)", token)
        if measurement:
            normalized.extend((measurement.group(1), unit_aliases.get(measurement.group(2), measurement.group(2))))
            continue
        token = unit_aliases.get(token, token)
        if token not in SEARCH_STOP_WORDS and len(token) > 1:
            normalized.append(token)
    return normalized


@lru_cache(maxsize=20_000)
def token_similarity(left, right):
    if left == right:
        return 1.0
    if min(len(left), len(right)) < 3:
        return 0.0
    return SequenceMatcher(None, left, right, autojunk=False).ratio()


def fuzzy_match(query, product):
    """Return a fuzzy score and a concise explanation tied to current query text."""
    query_tokens = list(dict.fromkeys(normalize_tokens(query)))
    if not query_tokens:
        return 0.0, ""

    fields = (
        ("title", product.get("title"), 1.0),
        ("category", product.get("category"), 0.85),
        ("description", product.get("description"), 0.6),
    )
    tokenized_fields = [(name, normalize_tokens(value), weight) for name, value, weight in fields]
    evidence = []
    score = 0.0

    for query_token in query_tokens:
        best = (0.0, "", "")
        for field_name, field_tokens, weight in tokenized_fields:
            for candidate in field_tokens:
                similarity = token_similarity(query_token, candidate)
                weighted = similarity * weight
                if similarity >= FUZZY_TOKEN_THRESHOLD and weighted > best[0]:
                    best = (weighted, field_name, candidate)
        score += best[0]
        if best[1]:
            evidence.append((query_token, best[2], best[1], best[0]))

    score /= len(query_tokens)
    query_phrase = " ".join(query_tokens)
    normalized_title = " ".join(normalize_tokens(product.get("title")))
    if query_phrase and query_phrase in normalized_title:
        score = min(1.0, score + 0.15)

    evidence.sort(key=lambda item: item[3], reverse=True)
    explanations = []
    for query_token, matched_token, field_name, _ in evidence:
        if query_token == matched_token:
            explanation = f'“{query_token}” in the {field_name}'
        else:
            explanation = f'“{query_token}” matching “{matched_token}” in the {field_name}'
        if explanation not in explanations:
            explanations.append(explanation)
        if len(explanations) == 2:
            break
    reason = "Matched " + " and ".join(explanations) + "." if explanations else ""
    return score, reason


def filter_by_category(query, products, category_source=None):
    """When a query names a catalog category, keep results from that category."""
    requested_type = product_type(query)
    if requested_type:
        # Intent is independent of which categories happen to be in the catalog.
        return [product for product in products if listing_type(product) == requested_type]
    query_tokens = list(dict.fromkeys(normalize_tokens(query)))
    category_tokens = {
        token
        for product in (category_source or products)
        for token in normalize_tokens(product.get("category"))
    }
    category_intent = {
        query_token
        for query_token in query_tokens
        if any(token_similarity(query_token, category_token) >= 0.72 for category_token in category_tokens)
    }
    if not category_intent:
        return products

    matching_products = [
        product
        for product in products
        if any(
            token_similarity(query_token, category_token) >= 0.72
            for query_token in category_intent
            for category_token in normalize_tokens(product.get("category"))
        )
    ]
    return matching_products


def is_non_price_unit_after(match, query):
    remainder = query[match.end():].lstrip()
    units = (
        r"(?i)(?:gb|gib|gigabytes?|mb|mib|megabytes?|tb|tib|terabytes?|"
        r"kb|kilobytes?|ram|memory|cores?|threads?|ghz|mhz|hz|watts?|"
        r"w|inches?|inch|cm|mm|kg|lbs?|pounds?|grams?|years?)\b"
    )
    return bool(re.match(units, remainder))


MEMORY_SIZE = r"(?P<amount>\d+(?:\.\d+)?)\s*(?:gibibytes?|gib|gigabytes?|gb)"
MEMORY_QUALIFIER = (
    r"(?P<qualifier>at\s+least|minimum(?:\s+of)?|min|at\s+most|up\s+to|"
    r"maximum|max|under|below|less\s+than|over|above|more\s+than|greater\s+than)?"
)


def parse_memory_condition(query):
    patterns = (
        re.compile(
            rf"\b{MEMORY_QUALIFIER}\s*{MEMORY_SIZE}\s+(?:of\s+)?"
            rf"(?:(?:unified|system|shared)\s+)?(?:memory|ram)\b",
            re.IGNORECASE,
        ),
        re.compile(
            rf"\b(?:memory|ram)\s*(?:of|at|:)?\s*{MEMORY_QUALIFIER}\s*{MEMORY_SIZE}\b",
            re.IGNORECASE,
        ),
    )
    for pattern in patterns:
        match = pattern.search(query)
        if not match:
            continue
        qualifier = (match.group("qualifier") or "").casefold()
        amount = Decimal(match.group("amount"))
        if any(word in qualifier for word in ("under", "below", "less than")):
            condition = {"maximum": amount, "maximum_exclusive": True}
        elif any(word in qualifier for word in ("at most", "up to", "maximum", "max")):
            condition = {"maximum": amount, "maximum_exclusive": False}
        elif any(word in qualifier for word in ("over", "above", "more than", "greater than")):
            condition = {"minimum": amount, "minimum_exclusive": True}
        else:
            condition = {"minimum": amount, "minimum_exclusive": False}
        remaining_query = query[:match.start()] + " " + query[match.end():]
        return condition, remaining_query
    return None, query


def parse_cheap_preference(query):
    pattern = re.compile(
        r"\b(?:cheap(?:est)?|inexpensive|affordable|budget(?:-friendly)?|low[- ]cost|low[- ]priced)\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(query)), pattern.sub(" ", query)


def extract_memory_gb(product):
    patterns = (
        re.compile(
            r"\b(\d+(?:\.\d+)?)\s*(?:gibibytes?|gib|gigabytes?|gb)\s+"
            r"(?:(?:of|unified|system|shared)\s+)?(?:memory|ram)\b",
            re.IGNORECASE,
        ),
        re.compile(
            r"\b(?:memory|ram)\s*(?:of|at|:)?\s*(\d+(?:\.\d+)?)\s*"
            r"(?:gibibytes?|gib|gigabytes?|gb)\b",
            re.IGNORECASE,
        ),
    )
    # The selected listing title takes priority over a generic description
    # mentioning other configurations (e.g. 'available in 8, 16 and 24 GB').
    for field in ("title", "description"):
        text = str(product.get(field) or "")
        amounts = set()
        for pattern_index, pattern in enumerate(patterns):
            for match in pattern.finditer(text):
                # '24GB RAM 512GB SSD' must not turn RAM+512GB into a
                # second memory claim; RAM already belongs to the preceding 24GB.
                if pattern_index == 1 and re.search(r"\d\s*(?:gb|gib)\s*$", text[:match.start()], re.I):
                    continue
                amounts.add(Decimal(match.group(1)))
        if amounts:
            return next(iter(amounts)) if len(amounts) == 1 else None
    return None


def apply_identity_requirements(query, products):
    """Explicit Apple chip/family requirements cannot be overridden by fuzzy/AI matches.

    Use the selected listing title as evidence, not generic descriptions listing
    compatibility with other devices. Missing evidence remains a non-match.
    """
    chip_pattern = r"\bm[1-9]\d?(?:\s+(?:pro|max|ultra))?\b"
    requested_chips = {" ".join(m.group().lower().split()) for m in re.finditer(chip_pattern, query, re.I)}
    family = re.search(r"\bmacbook\s+(air|pro)\b", query, re.I)
    filtered = []
    for product in apply_requirements(query, products):
        title = str(product.get("title") or "")
        title_chips = {" ".join(m.group().lower().split()) for m in re.finditer(chip_pattern, title, re.I)}
        if requested_chips and not requested_chips.issubset(title_chips):
            continue
        if family and not re.search(r"\bmacbook\s+" + family.group(1) + r"\b", title, re.I):
            continue
        filtered.append(product)
    return filtered


def apply_memory_condition(products, condition):
    if not condition:
        return products
    filtered = []
    minimum = condition.get("minimum")
    maximum = condition.get("maximum")
    for product in products:
        capacity = extract_memory_gb(product)
        if capacity is None:
            continue
        if minimum is not None and (
            capacity <= minimum if condition.get("minimum_exclusive") else capacity < minimum
        ):
            continue
        if maximum is not None and (
            capacity >= maximum if condition.get("maximum_exclusive") else capacity > maximum
        ):
            continue
        result = dict(product)
        previous_reason = result.get("match_reason", "")
        if minimum is not None and maximum is not None:
            requirement = f"between {minimum:g} and {maximum:g} GB of memory"
        elif minimum is not None:
            requirement = f"at least {minimum:g} GB of memory"
        else:
            requirement = f"at most {maximum:g} GB of memory"
        reason = f"Has {capacity:g} GB of memory, meeting your {requirement} requirement."
        result["match_reason"] = " ".join(part for part in (previous_reason, reason) if part)
        filtered.append(result)
    return filtered


def select_cheap_products(products):
    """Keep the lowest-priced 30% of the already-matched product set."""
    if not products:
        return []
    ordered = sorted(products, key=lambda product: float(product["price"]))
    if len(ordered) == 1:
        selected = ordered
        reason = "Only matching product found; no relative price comparison is available."
    else:
        count = max(1, math.floor(len(ordered) * 0.49))
        selected = ordered[:count]
        reason = f"Among {len(ordered)} matching products, this is one of the lowest-priced {count}."
    for product in selected:
        result_reason = product.get("match_reason", "")
        product["match_reason"] = " ".join(part for part in (result_reason, reason) if part)
    return selected


def parse_price_condition(query):
    between = re.search(
        rf"\bbetween\s+{PRICE_AMOUNT}\s+(?:and|to)\s+{PRICE_AMOUNT}",
        query,
        re.IGNORECASE,
    )
    if between:
        low, high = (Decimal(value.replace(",", "")) for value in between.groups())
        if low > high:
            low, high = high, low
        return {"minimum": low, "maximum": high}, query[:between.start()] + " " + query[between.end():]

    operators = (
        ("maximum", r"\b(?:under|below|less\s+than|cheaper\s+than)\s+", True),
        ("maximum", r"\b(?:at\s+most|up\s+to|maximum|max)\s+", False),
        ("minimum", r"\b(?:over|above|more\s+than|greater\s+than)\s+", True),
        ("minimum", r"\b(?:at\s+least|minimum|min)\s+", False),
    )
    for bound, operator, exclusive in operators:
        match = re.search(operator + PRICE_AMOUNT, query, re.IGNORECASE)
        if match and not is_non_price_unit_after(match, query):
            amount_text = re.search(PRICE_AMOUNT, match.group(0), re.IGNORECASE).group(1)
            amount = Decimal(amount_text.replace(",", ""))
            condition = {bound: amount, f"{bound}_exclusive": exclusive}
            return condition, query[:match.start()] + " " + query[match.end():]

    return None, query


def apply_price_condition(products, condition):
    if not condition:
        return products
    filtered = []
    for product in products:
        try:
            price = Decimal(str(product.get("price", "")))
        except InvalidOperation:
            continue
        minimum = condition.get("minimum")
        maximum = condition.get("maximum")
        if minimum is not None and (
            price <= minimum if condition.get("minimum_exclusive") else price < minimum
        ):
            continue
        if maximum is not None and (
            price >= maximum if condition.get("maximum_exclusive") else price > maximum
        ):
            continue
        if minimum is not None and maximum is not None:
            reason = f"Priced at ${price:,.2f}, within your ${minimum:,.2f}–${maximum:,.2f} range."
        elif maximum is not None:
            qualifier = "below" if condition.get("maximum_exclusive") else "at or below"
            reason = f"Priced at ${price:,.2f}, {qualifier} your ${maximum:,.2f} limit."
        else:
            qualifier = "above" if condition.get("minimum_exclusive") else "at or above"
            reason = f"Priced at ${price:,.2f}, {qualifier} your ${minimum:,.2f} minimum."
        result = dict(product)
        previous_reason = result.get("match_reason", "")
        result["match_reason"] = " ".join(part for part in (previous_reason, reason) if part)
        filtered.append(result)
    return filtered


def search_products(query, catalog=None, allow_model=True):
    original_query = query
    candidate_scope = catalog is not None
    cheap_preference, query = parse_cheap_preference(query)
    memory_condition, remaining_query = parse_memory_condition(query)
    price_condition, text_query = parse_price_condition(remaining_query)
    database = load_database_config()
    if catalog is None:
        catalog = load_catalog(database)
    category_catalog = apply_identity_requirements(original_query, filter_by_category(text_query, catalog))
    intent = parse_requirements(original_query)
    if not category_catalog and (intent["product_type"] or intent["specs"] or re.search(r"\bm[1-9]\d?\b|\bmacbook\s+(?:air|pro)\b", original_query, re.I)):
        # The loaded candidates/catalog contain no evidence for the explicit
        # identity. Asking a model for synonyms cannot establish that identity.
        return []
    matching_memory_products = apply_memory_condition(category_catalog, memory_condition)
    if memory_condition and not matching_memory_products:
        return []
    ranked = []
    for catalog_product in matching_memory_products:
        product = dict(catalog_product)
        cached_reason = product.pop("match_reason", "")
        memory_reason = cached_reason if memory_condition else ""
        if price_condition:
            price_matches = apply_price_condition([product], price_condition)
            if not price_matches:
                continue
            product = price_matches[0]
            price_reason = product.pop("match_reason", "")
        else:
            price_reason = ""
        score, reason = fuzzy_match(text_query, product)
        if score >= 0.18:
            product["match_reason"] = " ".join(
                part for part in (reason, memory_reason, price_reason) if part
            )
            ranked.append((score, product))

    ranked.sort(key=lambda item: (-item[0], float(item[1]["price"])))
    if ranked:
        if cheap_preference:
            cheap_matches = select_cheap_products([product for _, product in ranked])
            return cheap_matches[:MAX_RESULTS]
        return [product for _, product in ranked[:MAX_RESULTS]]

    if (price_condition or memory_condition or cheap_preference) and not normalize_tokens(text_query):
        products = [dict(product) for product in apply_identity_requirements(original_query, catalog)]
        if not memory_condition:
            for product in products:
                product.pop("match_reason", None)
        products = apply_memory_condition(products, memory_condition)
        products = apply_price_condition(products, price_condition)
        if cheap_preference:
            products = select_cheap_products(products)
        products.sort(key=lambda product: float(product["price"]))
        return products[:MAX_RESULTS]

    # Keep the local model available as a slower fallback for conceptual searches
    # that have no useful token overlap with the catalog.
    if not allow_model:
        return []
    return search_with_model_terms(
        text_query or query, database, price_condition, memory_condition, cheap_preference,
        candidate_products=catalog if candidate_scope else None,
        original_query=original_query,
    )


def search_with_model_terms(
    query, database, price_condition=None, memory_condition=None, cheap_preference=False,
    candidate_products=None, original_query=None,
):
    terms = interpret_query(query)
    if candidate_products is not None:
        # Keep model-expanded searches inside THIS request's candidate set.
        # Model terms cannot introduce unseen URLs or different catalog records.
        products = []
        for candidate in candidate_products:
            if any(fuzzy_match(term, candidate)[0] >= 0.5 for term in terms):
                product = dict(candidate)
                _, reason = fuzzy_match(query, product)
                product["match_reason"] = reason or f'Suggested as a related result for “{query}”.'
                products.append(product)
        products = apply_identity_requirements(original_query or query, filter_by_category(query, products, candidate_products))
        products = apply_memory_condition(products, memory_condition)
        products = apply_price_condition(products, price_condition)
        if cheap_preference:
            products = select_cheap_products(products)
        return products[:MAX_RESULTS]
    filters = []
    for term in terms:
        pattern = f"*{term}*"
        filters.extend(
            [
                f"title.ilike.{pattern}",
                f"description.ilike.{pattern}",
                f"category.ilike.{pattern}",
            ]
        )
    result = requests.get(
        f"{database.url}/rest/v1/products",
        headers={
            "apikey": database.secret_key,
            "Authorization": f"Bearer {database.secret_key}",
        },
        params={
            "select": "id,title,description,image_url,price,currency,product_url,source,category,scraped_at",
            "or": f"({','.join(filters)})",
            "order": "price.asc",
            "limit": str(MAX_RESULTS),
        },
        timeout=20,
    )
    result.raise_for_status()
    products = apply_identity_requirements(
        original_query or query, filter_by_category(query, result.json(), load_catalog(database))
    )
    for product in products:
        _, reason = fuzzy_match(query, product)
        product["match_reason"] = reason or f'Suggested as a related result for “{query}”.'
    products = apply_memory_condition(products, memory_condition)
    products = apply_price_condition(products, price_condition)
    if cheap_preference:
        products = select_cheap_products(products)
    return products


def search_response(query):
    """Collect fresh retailer candidates, save them, then apply existing ranking."""
    database = load_database_config()
    _, discovery_query = parse_cheap_preference(query)
    _, discovery_query = parse_price_condition(discovery_query)
    discovery_query = re.sub(
        r"\b(\d+(?:\.\d+)?)\s*(gb|tb)\s*(?:of\s+)?(?:ram|memory)\b",
        r"\1\2", discovery_query, flags=re.I,
    )
    discovery_query = " ".join(
        word for word in discovery_query.split() if word.casefold() not in SEARCH_STOP_WORDS
    ) or query
    candidates, collection = collect_live_products(discovery_query, database)
    if collection["saved"]:
        # Another search should not use the five-minute pre-collection snapshot.
        with _catalog_lock:
            _catalog_cache["expires_at"] = 0
    if candidates:
        try:
            products = search_products(query, catalog=candidates)
        except (requests.RequestException, ValueError):
            # Collection may succeed even when optional Ollama expansion fails.
            # Keep the successfully saved records, but don't show unranked items.
            products = search_products(query, catalog=candidates, allow_model=False)
            collection["errors"].append("Optional AI query expansion was unavailable; only direct matches are shown.")
    else:
        try:
            products = search_products(query)
        except (requests.RequestException, ValueError):
            # Cached search must still work without the optional local model.
            # If Supabase itself is unavailable this second direct attempt raises
            # its normal API error instead of pretending there are no products.
            products = search_products(query, allow_model=False)
            collection["errors"].append("Ollama query expansion was unavailable; only direct catalog matches are shown.")
    collection["matched"] = len(products)
    products = correct_legacy_categories(products)
    intent = parse_requirements(query)
    collection["requirements"] = {
        "product_type": intent["product_type"],
        "specifications": [
            {"name": name, "value": str(value), "comparison": comparison}
            for name, value, comparison in intent["specs"]
        ],
    }
    if not products and (intent["product_type"] or intent["specs"]):
        collection["message"] = collection.get("message", "") + (
            " No listings could be verified against your product type and requested specifications; unrelated products were excluded."
        )
    return {"products": products, "collection": collection}


def walmart_products_response(query):
    """Return validated Walmart search-card results for the homepage."""
    records = discover_walmart_products(query, limit=6)
    products = []
    for record in records:
        record["category"] = infer_category(record["title"])
        products.append(CollectedProduct.model_validate(record).model_dump(mode="json"))
    return {"products": products}


def bestbuy_products_response(query):
    """Return validated Best Buy search-card results for the homepage."""
    records = discover_bestbuy_products(query, limit=6)
    products = []
    for record in records:
        record["category"] = infer_category(record["title"])
        products.append(CollectedProduct.model_validate(record).model_dump(mode="json"))
    return {"products": products}


class SearchHandler(BaseHTTPRequestHandler):
    def send_json(self, status, payload):
        encoded = json.dumps(payload).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(encoded)

    def do_POST(self):
        if self.path not in {
            "/api/search",
            "/api/bestbuy-search",
            "/api/walmart-search",
        }:
            self.send_json(404, {"error": "Not found."})
            return
        try:
            length = int(self.headers.get("Content-Length", "0"))
            if length <= 0 or length > MAX_BODY_BYTES:
                self.send_json(400, {"error": "Search query is empty or too long."})
                return
            payload = json.loads(self.rfile.read(length))
            query = payload.get("query", "") if isinstance(payload, dict) else ""
            if not isinstance(query, str) or not query.strip() or len(query) > 300:
                self.send_json(400, {"error": "Enter a search query under 300 characters."})
                return
            if self.path == "/api/bestbuy-search":
                self.send_json(200, bestbuy_products_response(query.strip()))
            elif self.path == "/api/walmart-search":
                self.send_json(200, walmart_products_response(query.strip()))
            else:
                self.send_json(200, search_response(query.strip()))
        except ConfigurationError as error:
            self.send_json(503, {"error": str(error)})
        except requests.ConnectionError as error:
            if "11434" in str(error):
                message = "Ollama is not running locally. Start Ollama and try again."
            else:
                message = "Could not connect to Ollama or Supabase. Check that both are available."
            self.send_json(503, {"error": message})
        except requests.Timeout:
            self.send_json(504, {"error": "Search timed out. Try again in a moment."})
        except requests.HTTPError as error:
            response_url = error.response.url if error.response is not None else ""
            if "11434" in response_url:
                message = f"Ollama could not load {MODEL}. Run `ollama pull {MODEL}` and try again."
                status = 503
            elif error.response is not None and error.response.status_code >= 500:
                message = "The local model or Supabase returned an error. Check the local services."
                status = 502
            else:
                message = "Supabase rejected the search request. Check its table access and credentials."
                status = 502
            self.send_json(status, {"error": message})
        except (DiscoveryError, WalmartDiscoveryError) as error:
            self.send_json(502, {"error": str(error)})
        except (json.JSONDecodeError, ValueError):
            self.send_json(502, {"error": "The local model returned an invalid response. Try again."})
        except Exception:
            self.send_json(500, {"error": "Local search failed. Check the API terminal for details."})

    def do_GET(self):
        if self.path != "/api/deals":
            self.send_json(404, {"error": "Not found."})
            return
        try:
            database = load_database_config()
            catalog = load_catalog(database)
            bestbuy_products, walmart_products, discovery_errors = (
                discover_homepage_products()
            )
            bestbuy_products = validate_retailer_products(bestbuy_products)
            walmart_products = validate_retailer_products(walmart_products)
            collections = deal_collections(
                catalog,
                bestbuy_products=bestbuy_products,
                walmart_products=walmart_products,
            )
            self.send_json(
                200,
                {
                    "collections": collections,
                    "discovery_errors": discovery_errors,
                },
            )
        except ConfigurationError as error:
            self.send_json(503, {"error": str(error)})
        except requests.ConnectionError:
            self.send_json(503, {"error": "Could not connect to Supabase. Check its availability."})
        except requests.Timeout:
            self.send_json(504, {"error": "Loading homepage products timed out. Try again in a moment."})
        except requests.HTTPError:
            self.send_json(502, {"error": "Supabase rejected the homepage product request. Check its table access and credentials."})
        except requests.RequestException:
            self.send_json(502, {"error": "The homepage product request failed. Check the local API and Supabase connection."})

    def log_message(self, format, *args):
        print(f"[local-search] {format % args}")


if __name__ == "__main__":
    try:
        load_database_config()
    except ConfigurationError as error:
        raise SystemExit(str(error)) from None
    print(f"Shoppie local search API listening at http://{HOST}:{PORT}")
    print(f"Using Ollama model: {MODEL}")
    ThreadingHTTPServer((HOST, PORT), SearchHandler).serve_forever()
