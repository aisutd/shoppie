"""Explicit instructor-backend access to public.products; no import-time requests."""

from dataclasses import dataclass, field

import requests

from scraper.config import DatabaseConfig
from scraper.validator import Laptop


@dataclass(frozen=True)
class Database:
    url: str
    secret_key: str = field(repr=False)


class DatabaseError(ValueError):
    """A curated error safe to display without raw request/response details."""


def connect(config: DatabaseConfig):
    """Prepare backend settings locally. Only check/upsert functions make requests."""
    return Database(config.url, config.secret_key)


def request_headers(database):
    # Modern secret keys go in apikey, not Authorization: Bearer (they are not JWTs).
    return {"apikey": database.secret_key, "Accept": "application/json"}


def raise_response_error(response):
    """Classify known HTTP/PostgREST errors without printing server messages."""
    try:
        payload = response.json()
        code = payload.get("code") if isinstance(payload, dict) else None
        if not isinstance(code, str):
            code = None
    except ValueError:
        code = None
    status = response.status_code
    if status == 401 or code in {"PGRST301", "PGRST302", "PGRST303"}:
        raise DatabaseError("AUTHENTICATION FAILURE: the project rejected the secret key (HTTP 401/auth error). Check that it is valid for this project.")
    if status == 403 or code == "42501":
        raise DatabaseError("PERMISSION FAILURE: access to products was denied. Check the backend role's table grants.")
    if code in {"42P01", "PGRST205"}:
        raise DatabaseError("MISSING TABLE: public.products is missing or unavailable in the Data API schema cache. Check sql/schema.sql and table exposure.")
    if code == "PGRST204" or code == "42703":
        raise DatabaseError("SCHEMA FAILURE: products does not have the requested columns. Inspect its existing schema.")
    raise DatabaseError(f"CONNECTION/REQUEST FAILURE: Supabase returned HTTP {status}. Check project availability and Data API configuration.")


def check_database(database: Database):
    """A single read-only query; empty products tables also count as accessible."""
    try:
        response = requests.get(
            f"{database.url}/rest/v1/products",
            params={"select": "id", "limit": "1"},
            headers=request_headers(database), timeout=25, allow_redirects=False,
        )
    except requests.Timeout:
        raise DatabaseError("CONNECTION FAILURE: the products read timed out.") from None
    except requests.RequestException:
        raise DatabaseError("CONNECTION FAILURE: could not reach the configured project's Data API. Check the URL, network and project status.") from None
    if response.status_code not in (200, 206):
        raise_response_error(response)
    try:
        rows = response.json()
    except ValueError:
        raise DatabaseError("CONNECTION/RESPONSE FAILURE: expected a JSON products response.") from None
    if not isinstance(rows, list):
        raise DatabaseError("CONNECTION/RESPONSE FAILURE: expected a products result list.")
    # Do not print or return product rows; this command is only a connectivity check.


def upsert_product(database: Database, product: Laptop):
    if not isinstance(product, Laptop):
        raise ValueError("Only a validated Laptop may be saved.")
    row = {
        "retailer": f"{product.retailer}.com","product_id": product.product_id,"product_url": product.product_url,
        "title": product.title, "price": str(product.price), "currency": product.currency,"seller": f"{product.seller}.com",
        "category": "laptops", "scraped_at": product.observed_at.isoformat(),"availability": product.availability,
    }
    headers = request_headers(database)
    headers["Prefer"] = "resolution=merge-duplicates,return=minimal"
    try:
        response = requests.post(
            f"{database.url}/rest/v1/products",
            params={"on_conflict": "product_url"}, headers=headers,
            json=row, timeout=25, allow_redirects=False,
        )
    except requests.RequestException:
        raise DatabaseError("CONNECTION FAILURE: upsert result may be unknown. Check the table before retrying.") from None
    if response.status_code not in (200, 201, 204):
        raise_response_error(response)
