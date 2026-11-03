"""Local-only product search API backed by Ollama and the Supabase products table."""

import json
import math
import re
import threading
import time
from decimal import Decimal, InvalidOperation
from difflib import SequenceMatcher
from functools import lru_cache
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import requests

from scraper.config import ConfigurationError, load_database_config


HOST = "127.0.0.1"
PORT = 8001
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
    text = " ".join(str(product.get(field) or "") for field in ("title", "description"))
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
    amounts = [Decimal(match.group(1)) for pattern in patterns for match in pattern.finditer(text)]
    return max(amounts) if amounts else None


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


def search_products(query):
    cheap_preference, query = parse_cheap_preference(query)
    memory_condition, remaining_query = parse_memory_condition(query)
    price_condition, text_query = parse_price_condition(remaining_query)
    database = load_database_config()
    catalog = load_catalog(database)
    category_catalog = filter_by_category(text_query, catalog)
    matching_memory_products = apply_memory_condition(category_catalog, memory_condition)
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
        products = [dict(product) for product in catalog]
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
    return search_with_model_terms(
        text_query or query, database, price_condition, memory_condition, cheap_preference
    )


def search_with_model_terms(
    query, database, price_condition=None, memory_condition=None, cheap_preference=False
):
    terms = interpret_query(query)
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
    products = filter_by_category(query, result.json(), load_catalog(database))
    for product in products:
        _, reason = fuzzy_match(query, product)
        product["match_reason"] = reason or f'Suggested as a related result for “{query}”.'
    products = apply_memory_condition(products, memory_condition)
    products = apply_price_condition(products, price_condition)
    if cheap_preference:
        products = select_cheap_products(products)
    return products


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
        if self.path != "/api/search":
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
            self.send_json(200, {"products": search_products(query.strip())})
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
        except (json.JSONDecodeError, ValueError):
            self.send_json(502, {"error": "The local model returned an invalid response. Try again."})
        except Exception:
            self.send_json(500, {"error": "Local search failed. Check the API terminal for details."})

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
