"""Step 4: convert one raw listing into the shared database record.

Keep all basic normalization here for the beta. No SQL or product matching.
Raise ValueError naming the field when a record is invalid; never mutate input.
The exact output contract is documented in README.md.
"""

from datetime import datetime
from decimal import Decimal


def clean_text(value: object) -> str | None:
    """Clean optional text without inventing missing information."""
    # TODO: None -> None; reject nonstrings; trim/collapse whitespace.
    # Empty strings -> None. Keep identifiers as strings, including zeros.
    raise NotImplementedError("Mentee TODO: clean text")


def parse_money(value: object, currency: str | None) -> Decimal | None:
    """Convert an explicit USD amount into an exact decimal database value."""
    # TODO: None -> None. A present amount requires confirmed USD in beta.
    # TODO: Support JSON numbers and strings like '99.99' and '$1,099.99'.
    # Reject booleans, negative/nonfinite amounts, malformed comma placement,
    # financing/starting-at text, and more than two decimal places.
    # Decimal(str(value)) avoids binary-float arithmetic; zero is a real price.
    raise NotImplementedError("Mentee TODO: parse money")


def parse_timestamp(value: object) -> datetime:
    """Preserve observation time and convert it to a timezone-aware UTC value."""
    # TODO: Parse ISO 8601, including Z; reject missing timezone or invalid text.
    # TODO: Convert to UTC and truncate to microseconds consistently.
    # Do not replace scraped_at with the time the file is imported.
    raise NotImplementedError("Mentee TODO: parse timestamp")


def normalize_attributes(attributes: object) -> dict:
    """Standardize tech specifications while preserving unknown fields."""
    # TODO: None -> {}; otherwise require a dictionary and copy it.
    # Initial numeric fields: ram_gb, storage_gb, screen_inches, pack_quantity.
    # Accept plain numbers/numeric strings in the named canonical unit.
    # Add explicit unit conversions later; reject unsupported values clearly.
    # Clean color/connectivity text. Preserve unknown keys and missing values.
    # Condition is extracted separately by normalize(), not left in attributes.
    raise NotImplementedError("Mentee TODO: normalize attributes")


def normalize(record: dict) -> dict:
    """Produce listing details plus one observation for ingest.py."""
    # TODO: Require retailer_key, source_url, scraped_at and raw object.
    # Allowed keys: amazon, walmart, target, best_buy (match the fixture).
    # Require an absolute HTTP(S) URL; do not strip variant query parameters.
    # Identity for beta: retailer + stable URL for ONE selected offer/variant.
    # TODO: SHA-256 UTF-8 source_url -> source_url_hash (64 hex characters).
    # TODO: Map raw.model -> model_number; clean optional title/brand/GTIN/SKU.
    # TODO: Use helpers; read condition from raw.attributes.condition.
    # Condition: new, used, refurbished, open_box or None; reject unknown text.
    # Availability: in_stock, out_of_stock, unknown or None.
    # Optional raw.shipping_cost and raw.seller default to None.
    # Any known price/shipping requires USD. Missing currency with no amounts
    # is allowed. raw_payload must be a deep copy of the ORIGINAL full record.
    # Return exactly the README contract; no database writes in this function.
    raise NotImplementedError("Mentee TODO: normalize one listing")
