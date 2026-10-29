"""Validate one schema_version 1 listing without changing its source data."""

from copy import deepcopy
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from hashlib import sha256
import json
import math
import re
from urllib.parse import urlsplit

RETAILERS = {"amazon", "walmart", "target", "best_buy"}
RETAILER_HOSTS = {"amazon": "amazon.com", "walmart": "walmart.com",
                  "target": "target.com", "best_buy": "bestbuy.com"}
DEMO_HOSTS = {"amazon": "amazon.example", "walmart": "walmart.example",
              "target": "target.example", "best_buy": "best-buy.example"}
CONDITIONS = {"new", "used", "refurbished", "open_box"}
AVAILABILITY = {"in_stock", "out_of_stock", "unknown"}
CATEGORY_ALIASES = {"laptops": "laptop", "monitors": "monitor", "keyboards": "keyboard"}
NUMBER_ATTRIBUTES = {"ram_gb", "storage_gb", "screen_inches", "pack_quantity"}


def clean_text(value):
    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError("text field must be a string")
    return " ".join(value.split()) or None


def field_text(name, value):
    try:
        return clean_text(value)
    except ValueError:
        raise ValueError(f"{name} must be a string or null") from None


def parse_money(value, currency):
    if value is None:
        return None
    if currency != "USD":
        raise ValueError("currency must be USD when an amount is present")
    if isinstance(value, bool) or not isinstance(value, (str, int, float, Decimal)):
        raise ValueError("amount must be a number or price string")
    if isinstance(value, str):
        amount = value.strip()
        if not re.fullmatch(r"\$?(?:\d+|\d{1,3}(?:,\d{3})+)(?:\.\d{1,2})?", amount):
            raise ValueError("amount has an invalid price format")
        amount = amount.lstrip("$").replace(",", "")
    else:
        amount = str(value)
    try:
        number = Decimal(amount)
    except InvalidOperation:
        raise ValueError("amount is not a valid number") from None
    if not number.is_finite() or number < 0 or number >= Decimal("10000000000"):
        raise ValueError("amount must be finite, nonnegative, and fit DECIMAL(12,2)")
    if number.as_tuple().exponent < -2:
        raise ValueError("amount cannot have more than two decimal places")
    return number


def parse_timestamp(value):
    if not isinstance(value, str):
        raise ValueError("scraped_at must be an ISO 8601 timestamp")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        raise ValueError("scraped_at must be an ISO 8601 timestamp") from None
    if parsed.tzinfo is None or parsed.utcoffset() is None:
        raise ValueError("scraped_at must include a timezone")
    try:
        utc = parsed.astimezone(timezone.utc)
    except (OverflowError, ValueError):
        raise ValueError("scraped_at is outside the supported date range") from None
    if utc.year < 1000:
        raise ValueError("scraped_at is outside the MySQL DATETIME range")
    return utc


def normalize_attributes(attributes):
    if attributes is None:
        return {}
    if not isinstance(attributes, dict):
        raise ValueError("attributes must be an object")
    cleaned = deepcopy(attributes)
    for key in NUMBER_ATTRIBUTES:
        value = cleaned.get(key)
        if value is None:
            continue
        if isinstance(value, bool) or not isinstance(value, (str, int, float)):
            raise ValueError(f"attributes.{key} must be a positive number")
        if isinstance(value, str) and not re.fullmatch(r"\d+(?:\.\d+)?", value.strip()):
            raise ValueError(f"attributes.{key} must use its named unit")
        try:
            number = float(value)
        except ValueError:
            raise ValueError(f"attributes.{key} must be a positive number") from None
        if not math.isfinite(number) or number <= 0 or (key == "pack_quantity" and not number.is_integer()):
            raise ValueError(f"attributes.{key} must be a positive number")
        cleaned[key] = int(number) if number.is_integer() else number
    for key in ("color", "connectivity"):
        if key in cleaned:
            cleaned[key] = field_text(f"attributes.{key}", cleaned[key])
    return cleaned


def normalize(record):
    if not isinstance(record, dict):
        raise ValueError("listing must be an object")
    retailer = field_text("retailer_key", record.get("retailer_key"))
    if retailer not in RETAILERS:
        raise ValueError("retailer_key must name a configured retailer")
    url = field_text("source_url", record.get("source_url"))
    if not url or any(character.isspace() for character in url):
        raise ValueError("source_url must be an absolute HTTP(S) URL")
    try:
        parts = urlsplit(url)
        valid_url = parts.scheme in {"http", "https"} and parts.hostname and not parts.username and not parts.password and not parts.fragment
        if parts.port is not None and not 1 <= parts.port <= 65535:
            valid_url = False
    except ValueError:
        valid_url = False
    if not valid_url:
        raise ValueError("source_url must be an absolute HTTP(S) URL without credentials or fragment")
    host = parts.hostname.removeprefix("www.")
    if host not in {RETAILER_HOSTS[retailer], DEMO_HOSTS[retailer]}:
        raise ValueError("source_url host does not match retailer_key")
    scraped_at = parse_timestamp(record.get("scraped_at"))
    raw = record.get("raw")
    if not isinstance(raw, dict):
        raise ValueError("raw must be an object")
    try:
        json.dumps(record, allow_nan=False)
    except (TypeError, ValueError):
        raise ValueError("raw listing must contain valid JSON values") from None
    attributes = normalize_attributes(raw.get("attributes"))
    condition = field_text("attributes.condition", attributes.pop("condition", None))
    if condition not in CONDITIONS | {None}:
        raise ValueError("attributes.condition is not recognized")
    availability = field_text("availability", raw.get("availability"))
    if availability not in AVAILABILITY | {None}:
        raise ValueError("availability is not recognized")
    currency = field_text("currency", raw.get("currency"))
    if currency not in {None, "USD"}:
        raise ValueError("currency must be USD or null")
    try:
        price = parse_money(raw.get("price"), currency)
    except ValueError as error:
        raise ValueError(f"price: {error}") from None
    try:
        shipping = parse_money(raw.get("shipping_cost"), currency)
    except ValueError as error:
        raise ValueError(f"shipping_cost: {error}") from None
    category = field_text("category", raw.get("category"))
    if category:
        category = CATEGORY_ALIASES.get(category.casefold(), category.casefold())
    result = {
        "retailer_key": retailer,
        "retailer_sku": field_text("retailer_sku", record.get("retailer_sku")),
        "source_url": url,
        "source_url_hash": sha256(url.encode("utf-8")).hexdigest(),
        "title": field_text("title", raw.get("title")),
        "description": field_text("description", raw.get("description")),
        "brand": field_text("brand", raw.get("brand")),
        "model_number": field_text("model", raw.get("model")),
        "gtin": field_text("gtin", raw.get("gtin")),
        "category": category,
        "attributes": attributes,
        "scraped_at": scraped_at,
        "price": price,
        "shipping_cost": shipping,
        "currency": currency,
        "condition": condition,
        "seller": field_text("seller", raw.get("seller")),
        "availability": availability,
        "raw_payload": deepcopy(record),
    }
    limits = {"retailer_sku": 255, "brand": 255, "model_number": 255,
              "gtin": 32, "category": 100, "seller": 255}
    for field, limit in limits.items():
        if result[field] is not None and len(result[field]) > limit:
            raise ValueError(f"{field} exceeds {limit} characters")
    return result
