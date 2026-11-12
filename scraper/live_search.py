"""Bounded, request-scoped discovery -> extraction -> validation -> persistence.

No prompts, no model-generated URLs, no deletion of catalog rows. Every request
attempts discovery; a lock prevents simultaneous browser/network fan-out.
"""

import logging
import threading
import time
from datetime import datetime, timezone
from decimal import Decimal
from typing import Literal
from urllib.parse import urlsplit

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator

from scraper.bestbuy_search import DiscoveryError, MAX_PRODUCTS, discover_bestbuy_urls, recover_search_card
from scraper import tech_scraper


logger = logging.getLogger(__name__)
_collection_lock = threading.Lock()
COLLECTION_SECONDS = 55


class CollectedProduct(BaseModel):
    """Validate tech records before a web request is allowed to save them."""
    model_config = ConfigDict(extra="ignore", str_strip_whitespace=True)

    title: str = Field(min_length=5, max_length=1000)
    description: str | None = None
    image_url: str | None = None
    price: Decimal = Field(gt=0, max_digits=12, decimal_places=2, allow_inf_nan=False)
    currency: Literal["USD"]
    product_url: str
    source: Literal["bestbuy.com"]
    category: str
    scraped_at: datetime

    @field_validator("price", mode="before")
    @classmethod
    def reject_boolean(cls, value):
        if isinstance(value, bool):
            raise ValueError("Price must be a monetary amount.")
        return value

    @field_validator("product_url")
    @classmethod
    def valid_product_url(cls, value):
        value = tech_scraper.clean_url(value)
        if tech_scraper.identify_product(value)[0] != "bestbuy":
            raise ValueError("Expected a Best Buy product page.")
        return value

    @field_validator("image_url")
    @classmethod
    def https_image(cls, value):
        if value is None:
            return None
        parts = urlsplit(value)
        if parts.scheme != "https" or not parts.hostname or parts.username or parts.password or any(c.isspace() for c in value):
            raise ValueError("Expected an HTTPS image URL.")
        return value

    @field_validator("category")
    @classmethod
    def category_slug(cls, value):
        return tech_scraper.normalize_category(value)

    @field_validator("scraped_at")
    @classmethod
    def aware_time(cls, value):
        if value.utcoffset() is None:
            raise ValueError("Collection timestamp must include a timezone.")
        return value.astimezone(timezone.utc)


def infer_category(title):
    """Classify from the actual title, never label all search results laptops."""
    import re

    for category, pattern in (
        ("headphones", r"headphones?|earbuds?|airpods"),
        ("phones", r"iphone|smartphone|galaxy\s+s\d|pixel\s+\d"),
        ("tablets", r"ipad|tablet"),
        ("monitors", r"monitor"),
        ("laptops", r"laptop|notebook|macbook|chromebook|thinkpad|zenbook|vivobook|ideapad"),
        ("televisions", r"television|\btv\b"),
        ("keyboards", r"keyboard"),
    ):
        if re.search(pattern, title or "", re.I):
            return category
    return "electronics"


def collect_live_products(query, database, limit=MAX_PRODUCTS):
    """Return (fresh candidates, collection metadata); failures preserve catalog."""
    report = {
        "source": "bestbuy.com", "status": "failed", "discovered": 0,
        "collected": 0, "saved": 0, "failed": 0, "failed_saves": 0,
        "errors": [], "result_source": "catalog", "message": "", "recovered": 0,
    }
    if not _collection_lock.acquire(blocking=False):
        report.update(status="busy", message="Best Buy collection is busy. Showing stored catalog matches; try again shortly.")
        return [], report
    started = time.monotonic()
    products = []
    try:
        try:
            urls = discover_bestbuy_urls(query, limit=limit)
        except Exception as error:
            code = error.code if isinstance(error, DiscoveryError) else "unexpected_error"
            logger.warning("Best Buy discovery failed (%s)", code)
            report["failure_code"] = code
            report["errors"].append(
                str(error) if isinstance(error, DiscoveryError)
                else "Best Buy discovery encountered an unexpected error. Check the backend setup."
            )
            report["message"] = "Live Best Buy search failed. Showing stored catalog matches; prices were not refreshed."
            return [], report
        report["discovered"] = len(urls)
        if not urls:
            report.update(status="no_results", message="Best Buy returned no product links. Showing stored catalog matches.")
            return [], report
        for index, url in enumerate(urls):
            remaining = COLLECTION_SECONDS - (time.monotonic() - started)
            if remaining <= 2:
                report["failed"] += len(urls) - index
                report["errors"].append("Collection time budget reached; remaining pages were not checked.")
                break
            try:
                # Skip retailer-homepage warming so each candidate uses one request.
                recovered = False
                try:
                    html, final_url = tech_scraper.fetch_page(url, timeout=min(10, remaining), warmup=False)
                except ValueError as fetch_error:
                    # Recover transport errors only. Never retry a CAPTCHA,
                    # verification page or HTTP rejection through another route.
                    if "Page request failed or timed out:" not in str(fetch_error):
                        raise
                    remaining = COLLECTION_SECONDS - (time.monotonic() - started)
                    if remaining <= 2:
                        raise
                    raw = recover_search_card(url, timeout=min(8, remaining))
                    recovered = True
                if not recovered:
                    if (tech_scraper.identify_product(final_url) != tech_scraper.identify_product(url)
                            or urlsplit(final_url).query != urlsplit(url).query):
                        raise ValueError("Redirect changed the requested product/variant.")
                    raw = tech_scraper.extract_product(html, final_url)
                raw["category"] = infer_category(raw.get("title"))
                record = CollectedProduct.model_validate(raw).model_dump(mode="json")
                # Generated scraper UUIDs are not necessarily the persisted row ID.
                products.append(record)
                report["collected"] += 1
                if recovered:
                    report["recovered"] += 1
            except Exception as error:
                if isinstance(error, ValidationError):
                    fields = sorted({".".join(map(str, issue["loc"])) for issue in error.errors()})
                    reason = "invalid or missing " + ", ".join(fields)
                elif isinstance(error, ImportError):
                    reason = "a required scraper dependency is missing"
                elif isinstance(error, ValueError):
                    message = str(error)
                    if message.startswith("Public model search"):
                        reason = "the detail-page request failed and exact-product search-card recovery was unavailable"
                    elif "timed out" in message or "request failed" in message:
                        reason = "the product-page request failed or timed out"
                    elif "bot check" in message or "access-denied" in message:
                        reason = "the retailer returned a verification page"
                    elif "extract product title or price" in message:
                        reason = "the page did not contain an extractable title and price"
                    elif "Redirect changed" in message:
                        reason = "a redirect changed the selected product or variant"
                    else:
                        reason = "the product page could not be parsed"
                else:
                    reason = "an unexpected scraper error occurred"
                logger.warning("Best Buy candidate %d: %s (%s)", index + 1, reason, type(error).__name__)
                report["failed"] += 1
                report["errors"].append(f"Candidate {index + 1}: {reason}.")
                continue
            try:
                remaining = max(1, COLLECTION_SECONDS - (time.monotonic() - started))
                tech_scraper.upload_to_supabase(record, database=database, timeout=min(10, remaining))
                report["saved"] += 1
            except Exception:
                logger.warning("Best Buy candidate %d could not be saved", index + 1)
                report["failed_saves"] += 1
                report["errors"].append(f"Candidate {index + 1} was collected but its database save was not confirmed.")
        if products:
            partial = report["failed"] or report["failed_saves"]
            report.update(status="partial" if partial else "complete", result_source="live")
            report["message"] = (
                f"Checked {report['collected']} Best Buy listing(s) live; "
                f"{report['saved']} database save(s) confirmed."
            )
            if partial:
                report["message"] += " Some pages or saves failed; coverage is incomplete."
            if report["recovered"]:
                report["message"] += (
                    f" {report['recovered']} listing(s) recovered from exact-product Best Buy search cards because detail-page requests failed."
                )
        else:
            report["message"] = "No Best Buy pages could be validated. Showing stored catalog matches; prices were not refreshed."
        return products, report
    finally:
        _collection_lock.release()
